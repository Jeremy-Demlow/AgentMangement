"""
Generate incremental daily data for ski resort - ALL data types.
Uses shared constants and utilities for consistency with full generator.
Includes idempotency checks to prevent duplicate data.
"""

import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from snowflake_connection import SnowflakeConnection
from config import DATABASE, RAW_SCHEMA, get_database_for_env, VALID_ENVS

# Import shared constants and utilities
from shared import (
    get_rng, get_daily_modifier, get_snow_condition, calculate_wait_time,
    PERSONAS, LIFT_IDS, LIFT_CAPACITY, LIFT_POPULARITY,
    RENTAL_LOCS, FB_LOCS, RENTAL_PRODS, FB_PRODS, DAY_PASSES, TICKET_PRICES,
    WEATHER_ZONES, STAFFING_DEPARTMENTS, INSTRUCTOR_IDS, PARKING_LOT_INFO,
    TRAIL_NAMES, LESSON_TYPES, INCIDENT_TYPES, INCIDENT_SEVERITY,
    # Summer-specific imports
    SUMMER_MONTHS, SUMMER_TRAIL_NAMES, SUMMER_ACTIVITIES,
    SUMMER_INCIDENT_TYPES, SUMMER_LESSON_TYPES,
    SUMMER_TICKET_TYPES, SUMMER_TICKET_PRICES, SUMMER_RENTAL_ITEMS,
    SUMMER_FEEDBACK_CATEGORIES, SUMMER_FEEDBACK_SUBCATEGORIES,
    SUMMER_LIFT_IDS, SUMMER_LIFT_POPULARITY, SUMMER_STAFFING_DEPARTMENTS,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Use unseeded RNG for incremental (truly random daily data)
rng = get_rng()


# =============================================================================
# IDEMPOTENCY CHECK
#
# History: previously check_any_data_exists() short-circuited as soon as ONE
# of WEATHER/PASS_USAGE/LIFT_SCANS had the date. WEATHER is generated year-
# round (off-season too); PASS_USAGE/LIFT_SCANS only during ski season. So
# once weather was written for a date, ALL OTHER table writes for that date
# were silently skipped -- which is how CUSTOMER_FEEDBACK lost the entire
# 2025-2026 season after the SUBCATEGORY-NUMBER bug killed feedback writes
# specifically. Per-table presence + per-table generation gates fix that:
# the generator can self-heal a single missing table without needing --force.
# =============================================================================
def check_date_exists(conn, table_name, date_column, date_value):
    """Check if data for a specific date already exists in a table."""
    query = f"""
        SELECT COUNT(*) as cnt
        FROM {table_name}
        WHERE {date_column} = '{date_value}'
    """
    result = conn.sql(query).to_pandas()
    return result['CNT'].iloc[0] > 0


# Per-table date-column registry. Keys are presence-check tags used by the
# main loop; values are (snowflake_table, sql_expression_for_date_match).
# Add an entry here when adding a new generated table so the idempotency map
# stays in lockstep with what we write.
IDEMPOTENCY_TABLES = {
    "WEATHER_CONDITIONS":  ("WEATHER_CONDITIONS",  "WEATHER_DATE"),
    "STAFFING_SCHEDULE":   ("STAFFING_SCHEDULE",   "SCHEDULE_DATE"),
    "LIFT_MAINTENANCE":    ("LIFT_MAINTENANCE",    "MAINTENANCE_DATE"),
    "GROOMING_LOGS":       ("GROOMING_LOGS",       "GROOMING_DATE::DATE"),
    "LIFT_SCANS":          ("LIFT_SCANS",          "SCAN_TIMESTAMP::DATE"),
    "PASS_USAGE":          ("PASS_USAGE",          "VISIT_DATE"),
    "TICKET_SALES":        ("TICKET_SALES",        "PURCHASE_TIMESTAMP::DATE"),
    "FOOD_BEVERAGE":       ("FOOD_BEVERAGE",       "TRANSACTION_TIMESTAMP::DATE"),
    "RENTALS":             ("RENTALS",             "RENTAL_TIMESTAMP::DATE"),
    "SKI_LESSONS":         ("SKI_LESSONS",         "LESSON_DATE"),
    "INCIDENTS":           ("INCIDENTS",           "INCIDENT_DATE"),
    "CUSTOMER_FEEDBACK":   ("CUSTOMER_FEEDBACK",   "FEEDBACK_DATE::DATE"),
    "PARKING_OCCUPANCY":   ("PARKING_OCCUPANCY",   "RECORD_DATE::DATE"),
}


def present_for_date(conn, date) -> dict[str, bool]:
    """Return {table_tag: bool} indicating which tables already have data for
    this date. Use to drive per-table generation gates so a single missing
    table can be backfilled without re-writing tables that already have rows.

    Failures are treated as 'present' to avoid duplicate writes when a
    transient error blocks the check; --force still overrides everything.
    """
    date_str = date.strftime('%Y-%m-%d')
    out: dict[str, bool] = {}
    for tag, (table, col) in IDEMPOTENCY_TABLES.items():
        try:
            out[tag] = check_date_exists(conn, table, col, date_str)
        except Exception as exc:  # noqa: BLE001 - conservative on transient
            logger.debug("presence-check failed for %s/%s: %s; assuming present", table, col, exc)
            out[tag] = True
    return out


def check_any_data_exists(conn, date):
    """Backwards-compatible coarse check: True iff every checked table has
    data for the date. Retained for callers that still want the old
    'fully covered' question; new logic should prefer present_for_date().
    """
    return all(present_for_date(conn, date).values())


# =============================================================================
# DATA GENERATION FUNCTIONS
# =============================================================================
def generate_weather(date, daily_mod):
    """Generate weather records for all zones (year-round)."""
    records = []
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    is_summer = daily_mod.get('is_summer', False)

    for zone in WEATHER_ZONES:
        if is_summer:
            snowfall = 0.0
            base_depth = 0.0
            snow_condition = 'No Snow'
        else:
            snowfall = max(0.0, daily_mod['snowfall'] + rng.normal(0, 1.0))
            base_depth = max(18.0, 36 + rng.normal(0, 5.0))
            snow_condition = get_snow_condition(snowfall, date.month)

        temp_high = daily_mod['temp_high_f'] + int(rng.integers(-3, 4))
        temp_low = daily_mod['temp_low_f'] + int(rng.integers(-3, 4))
        wind_speed = int(rng.integers(3, 25))

        records.append({
            'WEATHER_DATE': date.strftime('%Y-%m-%d'),
            'MOUNTAIN_ZONE': zone,
            'SNOW_CONDITION': snow_condition,
            'SNOWFALL_INCHES': round(snowfall, 2),
            'BASE_DEPTH_INCHES': round(base_depth, 2),
            'TEMP_HIGH_F': float(temp_high),
            'TEMP_LOW_F': float(temp_low),
            'WIND_SPEED_MPH': float(wind_speed),
            'STORM_WARNING': daily_mod['storm_warning'],
            'CREATED_AT': created_at
        })

    return pd.DataFrame(records)


def generate_staffing(date, daily_mod):
    """Generate staffing records for the day (season-aware)."""
    entries = []
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    is_weekend = daily_mod['is_weekend']
    is_summer = daily_mod.get('is_summer', False)

    departments = SUMMER_STAFFING_DEPARTMENTS if is_summer else STAFFING_DEPARTMENTS
    for dept in departments:
        base = dept['base_staff']
        mult = dept['weekend_mult'] if is_weekend else 1.0
        scheduled = int(base * mult * daily_mod['season_mult'])
        actual = max(1, scheduled + int(rng.integers(-2, 3)))
        coverage = round(actual / max(scheduled, 1), 2)

        start_hour = 7 if dept['id'] == 'GRND' else 8
        end_hour = 16 if dept['id'] == 'GRND' else 17

        location_id = None
        if dept['location_pool']:
            location_id = rng.choice(dept['location_pool'])

        entries.append({
            'SCHEDULE_ID': f"STAFF{date.strftime('%Y%m%d')}{dept['id']}{int(rng.integers(0, 999)):03d}",
            'SCHEDULE_DATE': date.strftime('%Y-%m-%d'),
            'LOCATION_ID': location_id,
            'DEPARTMENT': dept['department'],
            'JOB_ROLE': dept['job_role'],
            'SCHEDULED_EMPLOYEES': scheduled,
            'ACTUAL_EMPLOYEES': actual,
            'COVERAGE_RATIO': coverage,
            'SHIFT_START': f"{date.strftime('%Y-%m-%d')} {start_hour:02d}:00:00",
            'SHIFT_END': f"{date.strftime('%Y-%m-%d')} {end_hour:02d}:00:00",
            'CREATED_AT': created_at
        })

    return pd.DataFrame(entries)


def generate_day_transactions(date, customers_df, daily_mod):
    """Generate ALL transaction types for a single day."""
    date_str = date.strftime('%Y%m%d')
    visit_date = date.strftime('%Y-%m-%d')
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Select visitors based on persona probabilities
    visitors = []
    for persona, config in PERSONAS.items():
        persona_customers = customers_df[customers_df['CUSTOMER_SEGMENT'] == persona]
        if len(persona_customers) == 0:
            continue

        if persona == 'weekend_warrior':
            if daily_mod['is_saturday']:
                base_prob = config['base_prob']['saturday']
            elif daily_mod['is_weekend']:
                base_prob = config['base_prob']['sunday']
            else:
                base_prob = config['base_prob']['weekday']
        else:
            base_prob = config['base_prob']['weekend'] if daily_mod['is_weekend'] else config['base_prob']['weekday']

        final_prob = base_prob * daily_mod['season_mult'] * daily_mod['holiday_mult'] * daily_mod['powder_boost']
        if daily_mod['storm_warning']:
            final_prob *= 0.7
        final_prob = min(0.9, final_prob)

        visit_mask = rng.random(len(persona_customers)) < final_prob
        if visit_mask.any():
            visitors.append(persona_customers[visit_mask])

    if not visitors:
        return None, None, None, None, None

    customers_today = pd.concat(visitors, ignore_index=True)
    n_visitors = len(customers_today)
    logger.info(f"  {visit_date}: {n_visitors} visitors (powder: {daily_mod['is_powder_day']}, weekend: {daily_mod['is_weekend']})")

    personas = customers_today['CUSTOMER_SEGMENT'].values
    customer_ids = customers_today['CUSTOMER_ID'].values
    is_pass_holder = customers_today['IS_PASS_HOLDER'].values if 'IS_PASS_HOLDER' in customers_today.columns else np.zeros(n_visitors, dtype=bool)

    # === LIFT SCANS ===
    lap_mins = np.array([PERSONAS[p]['laps_range'][0] for p in personas])
    lap_maxs = np.array([PERSONAS[p]['laps_range'][1] for p in personas])
    num_laps = rng.integers(lap_mins, lap_maxs + 1)
    total_scans = int(num_laps.sum())

    weather = 'Powder' if daily_mod['is_powder_day'] else 'Clear'

    # Generate lift assignments with popularity weighting
    lift_pop_array = np.array([LIFT_POPULARITY[lid] for lid in LIFT_IDS])
    lift_probs = lift_pop_array / lift_pop_array.sum()
    lift_assignments = rng.choice(LIFT_IDS, size=total_scans, p=lift_probs)

    # Generate hours with peak distribution (more scans 9am-1pm)
    hour_probs = np.array([0.05, 0.12, 0.18, 0.20, 0.18, 0.12, 0.08, 0.07])  # 8am-4pm
    hours = rng.choice(range(8, 16), size=total_scans, p=hour_probs)
    minutes = rng.integers(0, 60, size=total_scans)

    # Calculate wait times using shared function
    wait_times = calculate_wait_time(n_visitors, lift_assignments, hours, daily_mod, rng)

    scans_df = pd.DataFrame({
        'SCAN_ID': [f'SCAN{date_str}{i:08d}' for i in range(total_scans)],
        'CUSTOMER_ID': np.repeat(customer_ids, num_laps),
        'LIFT_ID': lift_assignments,
        'SCAN_TIMESTAMP': [f'{visit_date} {h:02d}:{m:02d}:00' for h, m in zip(hours, minutes)],
        'WAIT_TIME_MINUTES': wait_times,
        'TEMPERATURE_F': daily_mod['temp_low_f'] + rng.integers(0, 8, size=total_scans),
        'WEATHER_CONDITION': weather,
        'CREATED_AT': created_at
    })

    # === PASS USAGE ===
    usage_df = pd.DataFrame({
        'USAGE_ID': [f'USAGE{date_str}{cid}' for cid in customer_ids],
        'CUSTOMER_ID': customer_ids,
        'VISIT_DATE': visit_date,
        'FIRST_SCAN_TIME': [f'{visit_date} 08:{int(rng.integers(0, 60)):02d}:00' for _ in range(n_visitors)],
        'LAST_SCAN_TIME': [f'{visit_date} 15:{int(rng.integers(0, 60)):02d}:00' for _ in range(n_visitors)],
        'TOTAL_LIFT_RIDES': num_laps,
        'HOURS_ON_MOUNTAIN': np.clip(rng.uniform(4, 8, n_visitors), 2.5, 9.0).round(2),
        'CREATED_AT': created_at
    })

    # === TICKET SALES (non-pass holders) ===
    non_pass_mask = ~is_pass_holder
    n_tickets = non_pass_mask.sum()
    if n_tickets > 0:
        ticket_cids = customer_ids[non_pass_mask]
        channels = rng.choice(['online', 'window', 'kiosk'], size=n_tickets, p=[0.35, 0.60, 0.05])
        ticket_types = rng.choice(DAY_PASSES, size=n_tickets)
        amounts = np.array([TICKET_PRICES.get(t, 129) for t in ticket_types])

        sales_df = pd.DataFrame({
            'SALE_ID': [f'SALE{date_str}{i:06d}' for i in range(n_tickets)],
            'CUSTOMER_ID': ticket_cids,
            'TICKET_TYPE_ID': ticket_types,
            'LOCATION_ID': np.where(channels == 'online', 'LOC019', rng.choice(['LOC017', 'LOC018', 'LOC020'], size=n_tickets)),
            'PURCHASE_TIMESTAMP': [f'{visit_date} {int(rng.integers(7, 11)):02d}:{int(rng.integers(0, 60)):02d}:00' for _ in range(n_tickets)],
            'VALID_FROM_DATE': visit_date,
            'VALID_TO_DATE': visit_date,
            'PURCHASE_AMOUNT': amounts.astype(float),
            'PAYMENT_METHOD': rng.choice(['Credit Card', 'Debit Card', 'Cash'], size=n_tickets),
            'PURCHASE_CHANNEL': channels,
            'CREATED_AT': created_at
        })
    else:
        sales_df = pd.DataFrame()

    # === F&B TRANSACTIONS ===
    fb_counts = np.array([int(rng.integers(*PERSONAS[p]['fb_trans'])) for p in personas])
    total_fb = int(fb_counts.sum())

    fb_df = pd.DataFrame({
        'TRANSACTION_ID': [f'FB{date_str}{i:08d}' for i in range(total_fb)],
        'CUSTOMER_ID': np.repeat(customer_ids, fb_counts),
        'LOCATION_ID': rng.choice(FB_LOCS, size=total_fb),
        'PRODUCT_ID': rng.choice(FB_PRODS, size=total_fb),
        'TRANSACTION_TIMESTAMP': [f'{visit_date} {rng.choice([10,11,12,13,14,15]):02d}:{int(rng.integers(0, 60)):02d}:00' for _ in range(total_fb)],
        'QUANTITY': rng.integers(1, 3, total_fb),
        'UNIT_PRICE': rng.integers(5, 15, total_fb).astype(float),
        'TOTAL_AMOUNT': rng.integers(5, 30, total_fb).astype(float),
        'PAYMENT_METHOD': rng.choice(['Credit Card', 'Debit Card', 'Cash'], size=total_fb),
        'CREATED_AT': created_at
    })

    # === RENTALS ===
    rental_probs = np.array([PERSONAS[p]['rental_prob'] for p in personas])
    rental_mask = rng.random(n_visitors) < rental_probs
    n_rentals = rental_mask.sum()

    if n_rentals > 0:
        rent_df = pd.DataFrame({
            'RENTAL_ID': [f'RENT{date_str}{i:06d}' for i in range(n_rentals)],
            'CUSTOMER_ID': customer_ids[rental_mask],
            'LOCATION_ID': rng.choice(RENTAL_LOCS, size=n_rentals),
            'PRODUCT_ID': rng.choice(RENTAL_PRODS, size=n_rentals),
            'RENTAL_TIMESTAMP': f'{visit_date} 08:00:00',
            'RETURN_TIMESTAMP': f'{visit_date} 16:00:00',
            'RENTAL_DURATION_HOURS': 8.0,
            'RENTAL_AMOUNT': rng.integers(40, 70, n_rentals).astype(float),
            'CREATED_AT': created_at
        })
    else:
        rent_df = pd.DataFrame()

    return scans_df, usage_df, sales_df, fb_df, rent_df


def generate_ski_lessons(date, n_visitors, daily_mod, customers_df):
    """Generate ski lessons for the day."""
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    date_str = date.strftime('%Y-%m-%d')

    base_lessons = max(3, int(n_visitors * 0.08))
    if daily_mod['is_weekend']:
        base_lessons = int(base_lessons * 1.3)
    n_lessons = int(rng.integers(max(1, base_lessons - 3), base_lessons + 5))

    lesson_customers = customers_df.sample(n=min(n_lessons, len(customers_df)))['CUSTOMER_ID'].values

    records = []
    for i in range(n_lessons):
        lesson_type = rng.choice(LESSON_TYPES)
        start_hour = rng.choice([9, 10, 13, 14])
        duration = 2 if 'group' in lesson_type else int(rng.choice([1, 2, 3]))

        if lesson_type == 'private':
            group_size = int(rng.integers(1, 4))
            price = 150 + (group_size - 1) * 50
        elif lesson_type == 'kids_camp':
            group_size = int(rng.integers(4, 10))
            price = 120
        else:
            group_size = int(rng.integers(4, 12))
            price = 80

        rental_included = rng.random() < 0.4

        records.append({
            'LESSON_ID': f'LESSON{date.strftime("%Y%m%d")}{i:04d}',
            'CUSTOMER_ID': lesson_customers[i % len(lesson_customers)],
            'LESSON_DATE': date_str,
            'LESSON_START_TIME': f'{start_hour:02d}:00:00',
            'LESSON_TYPE': lesson_type,
            'SPORT_TYPE': rng.choice(['ski', 'ski', 'ski', 'snowboard']),
            'SKILL_LEVEL': rng.choice(['beginner', 'intermediate', 'advanced']),
            'DURATION_HOURS': float(duration),
            'INSTRUCTOR_ID': rng.choice(INSTRUCTOR_IDS),
            'GROUP_SIZE': group_size,
            'LESSON_AMOUNT': float(price),
            'RENTAL_INCLUDED': rental_included,
            'RENTAL_AMOUNT': float(45) if rental_included else 0.0,
            'TIP_AMOUNT': float(rng.choice([0, 10, 15, 20, 25])),
            'BOOKING_CHANNEL': rng.choice(['online', 'phone', 'walk_in']),
            'BOOKING_LEAD_DAYS': int(rng.integers(0, 14)),
            'COMPLETED': True,
            'CANCELLATION_REASON': None,
            'STUDENT_RATING': float(rng.choice([4.0, 4.5, 5.0, 4.5, 5.0])) if rng.random() < 0.7 else None,
            'CREATED_AT': created_at
        })

    return pd.DataFrame(records)


def generate_incidents(date, n_visitors, daily_mod, customers_df):
    """Generate safety incidents for the day."""
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    date_str = date.strftime('%Y-%m-%d')

    incident_rate = 0.002
    if daily_mod['is_powder_day']:
        incident_rate *= 1.3
    if daily_mod['storm_warning']:
        incident_rate *= 1.5

    n_incidents = max(0, int(rng.poisson(n_visitors * incident_rate)))

    records = []
    for i in range(n_incidents):
        incident_type = rng.choice(INCIDENT_TYPES, p=[0.35, 0.40, 0.08, 0.10, 0.05, 0.02])
        severity = rng.choice(INCIDENT_SEVERITY, p=[0.70, 0.25, 0.05])
        hour = int(rng.integers(9, 16))
        minute = int(rng.integers(0, 60))

        on_lift = rng.random() < 0.15
        lift_id = rng.choice(LIFT_IDS) if on_lift else None
        trail_name = None if on_lift else rng.choice(TRAIL_NAMES)

        records.append({
            'INCIDENT_ID': f'INC{date.strftime("%Y%m%d")}{i:04d}',
            'INCIDENT_DATE': date_str,
            'INCIDENT_TIME': f'{hour:02d}:{minute:02d}:00',
            'INCIDENT_TIMESTAMP': f'{date_str} {hour:02d}:{minute:02d}:00',
            'INCIDENT_TYPE': incident_type,
            'SEVERITY': severity,
            'LOCATION_ID': f'LOC{int(rng.integers(1, 20)):03d}',
            'LIFT_ID': lift_id,
            'TRAIL_NAME': trail_name,
            'CUSTOMER_ID': rng.choice(customers_df['CUSTOMER_ID'].values) if rng.random() < 0.8 else None,
            'CUSTOMER_AGE': int(rng.integers(8, 70)) if rng.random() < 0.8 else None,
            'CUSTOMER_SKILL_LEVEL': rng.choice(['beginner', 'intermediate', 'advanced', 'expert']),
            'DESCRIPTION': f'{incident_type.replace("_", " ").title()} incident',
            'CAUSE': rng.choice(['user_error', 'conditions', 'equipment', 'other']),
            'WEATHER_FACTOR': daily_mod['storm_warning'],
            'EQUIPMENT_FACTOR': incident_type == 'equipment_failure',
            'FIRST_AID_RENDERED': severity in ['moderate', 'serious'],
            'TRANSPORT_REQUIRED': severity == 'serious',
            'TRANSPORT_TYPE': 'toboggan' if severity == 'serious' else None,
            'PATROL_RESPONSE_MINUTES': int(rng.integers(3, 15)),
            'RESOLUTION': 'resolved',
            'FOLLOWUP_REQUIRED': severity == 'serious',
            'REPORT_FILED': True,
            'CREATED_AT': created_at
        })

    return pd.DataFrame(records)


def generate_customer_feedback(date, n_visitors, daily_mod, customers_df):
    """Generate customer feedback/surveys with realistic per-day distribution.

    Produces ~5% of daily visitors as feedback. Score distribution is
    correlated with weather + season conditions (powder days lift scores;
    storm warnings depress them). Text is sampled from category x sentiment
    banks below so feedback looks like real customer comments rather than
    placeholder strings -- demos can search/aggregate on FEEDBACK_TEXT.

    Schema preserved from prior version; only content quality changed.
    """
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    date_str = date.strftime('%Y-%m-%d')

    n_feedback = max(0, int(rng.poisson(n_visitors * 0.05)))
    if n_feedback == 0:
        return pd.DataFrame()

    # Category-aware subcategories so SUBCATEGORY analytics are coherent.
    # Mapping CATEGORY -> list[SUBCATEGORY] so a row like
    # CATEGORY='lift_operations' gets a lift-relevant subcategory.
    subcategories_by_category = {
        'lift_operations':    ['lift_lines', 'lift_speed', 'lift_reliability', 'staff_friendliness'],
        'food_service':       ['food_quality', 'food_value', 'service_speed', 'menu_variety'],
        'rental_shop':        ['equipment_quality', 'fitting_accuracy', 'wait_time', 'staff_knowledge'],
        'ski_school':         ['instructor_quality', 'lesson_pace', 'group_size', 'value_for_money'],
        'facilities':         ['cleanliness', 'parking', 'signage', 'restroom_availability'],
        'overall_experience': ['snow_quality', 'crowd_levels', 'overall_value', 'would_return'],
    }

    # Curated text banks: keyed by (category, sentiment_bucket).
    # sentiment_bucket: 'pos' (satisfaction>=4), 'neu' (3-4), 'neg' (<3).
    text_banks = {
        ('lift_operations', 'pos'): [
            "Lift lines moved fast even on a busy Saturday. Staff was efficient.",
            "The new high-speed quad is a game changer. Hardly any wait.",
            "Lift ops crew was friendly and kept things moving. Great experience.",
            "Loved how quickly they reopened the lifts after the wind hold.",
            "No-wait gondola access for pass holders is fantastic.",
        ],
        ('lift_operations', 'neu'): [
            "Lift lines were OK -- about 10 minutes most of the day.",
            "One lift was on slow speed which slowed things down a bit.",
            "Service was fine but nothing special. Average wait times.",
        ],
        ('lift_operations', 'neg'): [
            "Lift line at the main quad was 25+ minutes mid-morning. Too long.",
            "Two lifts were down for half the day with no clear announcement.",
            "Lift ops seemed understaffed; hard to find someone to ask about a stuck chair.",
            "Wind hold was understandable but communication was poor.",
        ],
        ('food_service', 'pos'): [
            "Food at the lodge was hot, fresh, and quick. Better than expected.",
            "The chili and cornbread combo was perfect after a cold morning.",
            "Loved the new ramen station -- worth every penny.",
            "Friendly staff at the cafeteria, great breakfast burrito.",
        ],
        ('food_service', 'neu'): [
            "Food was OK. Standard mountain fare for standard mountain prices.",
            "Burger was decent but $19 felt steep. Coffee was good though.",
        ],
        ('food_service', 'neg'): [
            "Food prices are out of control. $25 for a burger and fries.",
            "Long line at the lodge cafeteria; ran out of pizza by 1pm.",
            "Cold fries, lukewarm coffee. Not great for the price.",
            "The vegan options are very limited and overpriced.",
        ],
        ('rental_shop', 'pos'): [
            "Rental shop got me set up in 10 minutes. Skis were freshly waxed.",
            "Helpful boot fitter got my fit dialed on the first try.",
            "Snowboard rental was quality gear, not beat up at all.",
        ],
        ('rental_shop', 'neu'): [
            "Rental process was fine. Standard wait, standard equipment.",
            "Boots were OK -- not the most comfortable but worked for the day.",
        ],
        ('rental_shop', 'neg'): [
            "Waited 45 minutes for rentals on a Saturday. Need more staff.",
            "Skis they gave me were dull and the boots were too big.",
            "Rental return line was a mess. No one directing traffic.",
        ],
        ('ski_school', 'pos'): [
            "Our instructor for the kids was amazing. Patient and fun.",
            "Group lesson was excellent. Real progress in 2 hours.",
            "First time on skis and the instructor made it easy and safe.",
            "Private lesson worth every dollar -- huge improvement in technique.",
        ],
        ('ski_school', 'neu'): [
            "Lesson was OK. Group was a bit large but the instructor managed.",
            "Decent intro lesson but felt rushed at the end.",
        ],
        ('ski_school', 'neg'): [
            "Group lesson had 9 kids of mixed ability -- way too big.",
            "Instructor was fine but $130 for an hour seems steep.",
            "Lesson started 15 minutes late which ate into our time on snow.",
        ],
        ('facilities', 'pos'): [
            "Lodge was clean and warm. Bathrooms well stocked all day.",
            "Plenty of parking even on a Saturday morning. Easy in and out.",
            "Signage at trail intersections was clear and helpful.",
        ],
        ('facilities', 'neu'): [
            "Bathrooms were busy but clean enough. Could use more stalls.",
            "Parking lot was full by 9:30 -- arrive early.",
        ],
        ('facilities', 'neg'): [
            "Bathrooms were filthy by midday. Out of paper towels.",
            "Parking shuttle was unreliable and freezing waiting for it.",
            "Trail map signage is confusing -- got lost twice.",
        ],
        ('overall_experience', 'pos'): [
            "Best ski day of the season. Powder, blue skies, no lines.",
            "Will absolutely be back. Top to bottom an amazing day.",
            "Powder day lived up to the hype. Bluebird and bottomless.",
            "Family had a great time. Kids want to come back next weekend.",
        ],
        ('overall_experience', 'neu'): [
            "Decent day on the mountain. Snow was OK, lifts were OK.",
            "Good day but nothing memorable. Average all around.",
        ],
        ('overall_experience', 'neg'): [
            "Crowded, expensive, and the snow was icy. Not worth $180 a ticket.",
            "Tough day -- visibility was bad and lifts were down.",
            "Felt nickel-and-dimed all day. Won't return at these prices.",
        ],
    }

    response_templates = [
        "Thanks for the detailed feedback -- we're sharing this with the team.",
        "We appreciate you taking the time. We're working on this for next season.",
        "Sorry to hear that. We'd love to make it right -- email guestservices@ for a follow-up.",
        "Thank you! Glad you had a great day. See you next time.",
        "Noted and forwarded to the lift ops team.",
        "Apologies for the experience. A guest services rep will reach out.",
    ]

    visitor_ids = customers_df['CUSTOMER_ID'].values
    storm = bool(daily_mod.get('storm_warning', False))
    powder = bool(daily_mod.get('is_powder_day', False))

    records = []
    for i in range(n_feedback):
        # Score distribution shaped by conditions.
        base_rating = 4.0
        if powder:
            base_rating += 0.4
        if storm:
            base_rating -= 0.6

        nps = int(min(10, max(0, rng.normal(base_rating * 2, 1.5))))
        satisfaction = round(min(5.0, max(1.0, rng.normal(base_rating, 0.7))), 1)

        if satisfaction >= 4:
            sentiment, bucket = 'positive', 'pos'
        elif satisfaction < 3:
            sentiment, bucket = 'negative', 'neg'
        else:
            sentiment, bucket = 'neutral', 'neu'

        category = rng.choice(list(subcategories_by_category.keys()))
        subcategory = rng.choice(subcategories_by_category[category])

        # ~70% of feedback has text (was ~30%); when present, sampled from
        # the curated bank for this (category, sentiment) so the comment
        # actually looks plausible.
        if rng.random() < 0.7:
            bank = text_banks.get((category, bucket)) or text_banks[(category, 'neu')]
            feedback_text = str(rng.choice(bank))
        else:
            feedback_text = None

        # Response cadence: negatives get faster + more frequent responses.
        if sentiment == 'negative':
            response_prob, resolution_prob = 0.60, 0.55
            response_offset_h = float(rng.uniform(2, 24))
        elif sentiment == 'positive':
            response_prob, resolution_prob = 0.20, 0.85
            response_offset_h = float(rng.uniform(12, 72))
        else:
            response_prob, resolution_prob = 0.30, 0.70
            response_offset_h = float(rng.uniform(8, 48))

        has_response = rng.random() < response_prob
        response_text = str(rng.choice(response_templates)) if has_response else None
        response_date = (
            (date + timedelta(hours=response_offset_h)).strftime('%Y-%m-%d %H:%M:%S')
            if has_response else None
        )
        responded_by = f'STAFF{int(rng.integers(1, 50)):03d}' if has_response else None

        resolved = bool(rng.random() < resolution_prob)
        resolution_date = (
            (date + timedelta(hours=response_offset_h + rng.uniform(1, 168))).strftime('%Y-%m-%d %H:%M:%S')
            if resolved else None
        )

        records.append({
            'FEEDBACK_ID': f'FDBK{date.strftime("%Y%m%d")}{i:04d}',
            'CUSTOMER_ID': rng.choice(visitor_ids),
            'FEEDBACK_DATE': date_str,
            'FEEDBACK_TYPE': rng.choice(['survey', 'comment_card', 'email', 'app']),
            'SURVEY_ID': f'SURV{int(rng.integers(1, 100)):03d}',
            'NPS_SCORE': nps,
            'SATISFACTION_SCORE': satisfaction,
            'LIKELIHOOD_TO_RETURN': int(min(10, max(0, nps + int(rng.integers(-1, 2))))),
            'LIKELIHOOD_TO_RECOMMEND': nps,
            'CATEGORY': category,
            'SUBCATEGORY': subcategory,
            'SENTIMENT': sentiment,
            'SENTIMENT_SCORE': round(satisfaction / 5.0, 2),
            'FEEDBACK_TEXT': feedback_text,
            'RESPONSE_TEXT': response_text,
            'RESPONSE_DATE': response_date,
            'RESPONDED_BY': responded_by,
            'RESOLVED': resolved,
            'RESOLUTION_DATE': resolution_date,
            'ESCALATED': bool(satisfaction < 2.5),
            'SOURCE': rng.choice(['email', 'app', 'kiosk', 'web']),
            'VISIT_DATE': date_str,
            'CREATED_AT': created_at,
        })

    return pd.DataFrame(records)


def generate_parking_occupancy(date, n_visitors, daily_mod):
    """Generate hourly parking occupancy."""
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    date_str = date.strftime('%Y-%m-%d')

    records = []

    for lot_id, info in PARKING_LOT_INFO.items():
        capacity = info['capacity']
        lot_name = info['name']
        peak_cars = min(capacity, int(n_visitors / 2.5 * (capacity / 1250)))

        prev_occupied = 0
        for hour in range(7, 18):
            if hour <= 10:
                occupancy_pct = (hour - 7) / 3 * 0.9
            elif hour <= 15:
                occupancy_pct = 0.85 + rng.uniform(-0.1, 0.1)
            else:
                occupancy_pct = 0.85 - (hour - 15) * 0.25

            occupancy_pct = max(0.05, min(1.0, occupancy_pct))
            occupied = int(peak_cars * occupancy_pct)

            vehicles_entered = max(0, occupied - prev_occupied) if occupied > prev_occupied else int(rng.integers(0, 5))
            vehicles_exited = max(0, prev_occupied - occupied) if occupied < prev_occupied else int(rng.integers(0, 5))

            records.append({
                'RECORD_ID': f'PARK{date.strftime("%Y%m%d")}{lot_id}{hour:02d}',
                'RECORD_DATE': date_str,
                'RECORD_HOUR': hour,
                'LOT_ID': lot_id,
                'LOT_NAME': lot_name,
                'TOTAL_SPACES': capacity,
                'OCCUPIED_SPACES': occupied,
                'OCCUPANCY_PERCENT': round(occupied / capacity * 100, 1),
                'VEHICLES_ENTERED': vehicles_entered,
                'VEHICLES_EXITED': vehicles_exited,
                'REVENUE_COLLECTED': float(vehicles_entered * 20) if lot_id != 'PARK004' else 0.0,
                'OVERFLOW_ACTIVE': occupancy_pct > 0.95,
                'CREATED_AT': created_at
            })
            prev_occupied = occupied

    return pd.DataFrame(records)


def generate_lift_maintenance(date, daily_mod):
    """Generate lift maintenance logs."""
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    date_str = date.strftime('%Y-%m-%d')

    records = []
    for lift_id in LIFT_IDS:
        if rng.random() < 0.15:
            maint_type = rng.choice(['repair', 'replacement', 'adjustment'])
            downtime = int(rng.integers(30, 180))
            during_ops = rng.random() < 0.3
            parts_cost = float(rng.integers(100, 2000)) if maint_type == 'replacement' else 0.0
        else:
            maint_type = 'inspection'
            downtime = 0
            during_ops = False
            parts_cost = 0.0

        labor_hours = round(rng.uniform(0.5, 3.0), 1)
        labor_cost = float(labor_hours * 75)

        records.append({
            'MAINTENANCE_ID': f'MAINT{date.strftime("%Y%m%d")}{lift_id}',
            'LIFT_ID': lift_id,
            'MAINTENANCE_DATE': date_str,
            'MAINTENANCE_TYPE': maint_type,
            'CATEGORY': rng.choice(['mechanical', 'electrical', 'safety', 'routine']),
            'DESCRIPTION': f'Daily {maint_type} for {lift_id}',
            'START_TIME': f'{date_str} 06:00:00',
            'END_TIME': f'{date_str} 07:30:00',
            'DOWNTIME_MINUTES': downtime,
            'DURING_OPERATING_HOURS': during_ops,
            'PARTS_REPLACED': maint_type == 'replacement',
            'PARTS_COST': parts_cost,
            'LABOR_HOURS': labor_hours,
            'LABOR_COST': labor_cost,
            'TOTAL_COST': parts_cost + labor_cost,
            'TECHNICIAN_ID': f'TECH{int(rng.integers(1, 10)):03d}',
            'PASSED_INSPECTION': maint_type == 'inspection' or rng.random() < 0.95,
            'FOLLOWUP_REQUIRED': maint_type != 'inspection' and rng.random() < 0.1,
            'NOTES': f'{maint_type.title()} completed successfully' if rng.random() < 0.3 else None,
            'CREATED_AT': created_at
        })

    return pd.DataFrame(records)


def generate_grooming_logs(date, daily_mod):
    """Generate daily grooming logs."""
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    date_str = date.strftime('%Y-%m-%d')

    n_trails_groomed = min(len(TRAIL_NAMES), int(round(rng.normal(12, 2))))
    n_trails_groomed = max(5, n_trails_groomed)
    trails_groomed = list(rng.choice(TRAIL_NAMES, size=n_trails_groomed, replace=False))

    records = []
    for i, trail in enumerate(trails_groomed):
        start_hour = int(rng.integers(3, 6))
        end_hour = 7
        duration = (end_hour - start_hour) * 60 + int(rng.integers(-15, 30))

        records.append({
            'LOG_ID': f'GROOM{date.strftime("%Y%m%d")}{i:03d}',
            'GROOMING_DATE': date_str,
            'SHIFT': 'overnight',
            'TRAIL_NAME': trail,
            'GROOMER_ID': f'EMP{int(rng.integers(50, 60)):03d}',
            'MACHINE_ID': f'CAT{int(rng.integers(1, 6)):02d}',
            'START_TIME': f'{date_str} {start_hour:02d}:00:00',
            'END_TIME': f'{date_str} {end_hour:02d}:00:00',
            'DURATION_MINUTES': duration,
            'GROOMING_TYPE': rng.choice(['full', 'touch_up', 'edge_work']),
            'SNOW_DEPTH_INCHES': round(rng.uniform(24, 48), 1),
            'CONDITIONS_BEFORE': rng.choice(['good', 'fair', 'poor', 'icy']),
            'CONDITIONS_AFTER': rng.choice(['excellent', 'good', 'fair']),
            'FUEL_USED_GALLONS': round(rng.uniform(8, 25), 1),
            'NOTES': f'Groomed {trail}' if rng.random() < 0.2 else None,
            'CREATED_AT': created_at
        })

    return pd.DataFrame(records)


def generate_summer_transactions(date, customers_df, daily_mod):
    """Generate summer recreation transactions (bike park, hiking, scenic rides).
    Returns: (scans_df, usage_df, sales_df, fb_df, rent_df) same shape as winter.
    """
    date_str = date.strftime('%Y%m%d')
    visit_date = date.strftime('%Y-%m-%d')
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Select visitors using same persona probabilities (lower volume via season_mult)
    visitors = []
    for persona, config in PERSONAS.items():
        persona_customers = customers_df[customers_df['CUSTOMER_SEGMENT'] == persona]
        if len(persona_customers) == 0:
            continue

        if persona == 'weekend_warrior':
            if daily_mod['is_saturday']:
                base_prob = config['base_prob']['saturday']
            elif daily_mod['is_weekend']:
                base_prob = config['base_prob']['sunday']
            else:
                base_prob = config['base_prob']['weekday']
        else:
            base_prob = config['base_prob']['weekend'] if daily_mod['is_weekend'] else config['base_prob']['weekday']

        final_prob = base_prob * daily_mod['season_mult'] * daily_mod['holiday_mult']
        if daily_mod.get('is_rainy', False):
            final_prob *= 0.5
        final_prob = min(0.9, final_prob)

        visit_mask = rng.random(len(persona_customers)) < final_prob
        if visit_mask.any():
            visitors.append(persona_customers[visit_mask])

    if not visitors:
        return None, None, None, None, None

    customers_today = pd.concat(visitors, ignore_index=True)
    n_visitors = len(customers_today)
    logger.info(f"  {visit_date}: {n_visitors} summer visitors (rainy: {daily_mod.get('is_rainy', False)}, weekend: {daily_mod['is_weekend']})")

    personas = customers_today['CUSTOMER_SEGMENT'].values
    customer_ids = customers_today['CUSTOMER_ID'].values
    is_pass_holder = customers_today['IS_PASS_HOLDER'].values if 'IS_PASS_HOLDER' in customers_today.columns else np.zeros(n_visitors, dtype=bool)

    # === LIFT SCANS (gondola/bike uplift) ===
    # Summer visitors do fewer "laps" (scenic gondola rides or bike uplift runs)
    lap_mins = np.array([max(2, PERSONAS[p]['laps_range'][0] // 3) for p in personas])
    lap_maxs = np.array([max(4, PERSONAS[p]['laps_range'][1] // 3) for p in personas])
    num_laps = rng.integers(lap_mins, lap_maxs + 1)
    total_scans = int(num_laps.sum())

    weather = 'Sunny' if not daily_mod.get('is_rainy', False) else 'Rainy'

    # Assign to summer-operating lifts
    lift_pop_array = np.array([SUMMER_LIFT_POPULARITY[lid] for lid in SUMMER_LIFT_IDS])
    lift_probs = lift_pop_array / lift_pop_array.sum()
    lift_assignments = rng.choice(SUMMER_LIFT_IDS, size=total_scans, p=lift_probs)

    # Generate hours (summer hours: 9am-5pm, peak 10am-2pm)
    hour_probs = np.array([0.08, 0.14, 0.17, 0.18, 0.16, 0.12, 0.08, 0.05, 0.02])  # 9am-5pm
    hours = rng.choice(range(9, 18), size=total_scans, p=hour_probs)
    minutes = rng.integers(0, 60, size=total_scans)

    # Wait times are shorter in summer
    wait_times = np.clip(rng.uniform(1, 10, total_scans), 1, 15).round(1)

    scans_df = pd.DataFrame({
        'SCAN_ID': [f'SCAN{date_str}{i:08d}' for i in range(total_scans)],
        'CUSTOMER_ID': np.repeat(customer_ids, num_laps),
        'LIFT_ID': lift_assignments,
        'SCAN_TIMESTAMP': [f'{visit_date} {h:02d}:{m:02d}:00' for h, m in zip(hours, minutes)],
        'WAIT_TIME_MINUTES': wait_times,
        'TEMPERATURE_F': daily_mod['temp_low_f'] + rng.integers(5, 15, size=total_scans),
        'WEATHER_CONDITION': weather,
        'CREATED_AT': created_at
    })

    # === PASS USAGE ===
    usage_df = pd.DataFrame({
        'USAGE_ID': [f'USAGE{date_str}{cid}' for cid in customer_ids],
        'CUSTOMER_ID': customer_ids,
        'VISIT_DATE': visit_date,
        'FIRST_SCAN_TIME': [f'{visit_date} 09:{int(rng.integers(0, 60)):02d}:00' for _ in range(n_visitors)],
        'LAST_SCAN_TIME': [f'{visit_date} 16:{int(rng.integers(0, 60)):02d}:00' for _ in range(n_visitors)],
        'TOTAL_LIFT_RIDES': num_laps,
        'HOURS_ON_MOUNTAIN': np.clip(rng.uniform(3, 7, n_visitors), 2.0, 8.0).round(2),
        'CREATED_AT': created_at
    })

    # === TICKET SALES (summer passes) ===
    non_pass_mask = ~is_pass_holder
    n_tickets = non_pass_mask.sum()
    if n_tickets > 0:
        ticket_cids = customer_ids[non_pass_mask]
        channels = rng.choice(['online', 'window', 'kiosk'], size=n_tickets, p=[0.45, 0.45, 0.10])
        ticket_types = rng.choice(SUMMER_TICKET_TYPES, size=n_tickets)
        amounts = np.array([SUMMER_TICKET_PRICES.get(t, 55) for t in ticket_types])

        sales_df = pd.DataFrame({
            'SALE_ID': [f'SALE{date_str}{i:06d}' for i in range(n_tickets)],
            'CUSTOMER_ID': ticket_cids,
            'TICKET_TYPE_ID': ticket_types,
            'LOCATION_ID': np.where(channels == 'online', 'LOC019', rng.choice(['LOC017', 'LOC018', 'LOC020'], size=n_tickets)),
            'PURCHASE_TIMESTAMP': [f'{visit_date} {int(rng.integers(8, 12)):02d}:{int(rng.integers(0, 60)):02d}:00' for _ in range(n_tickets)],
            'VALID_FROM_DATE': visit_date,
            'VALID_TO_DATE': visit_date,
            'PURCHASE_AMOUNT': amounts.astype(float),
            'PAYMENT_METHOD': rng.choice(['Credit Card', 'Debit Card', 'Cash'], size=n_tickets),
            'PURCHASE_CHANNEL': channels,
            'CREATED_AT': created_at
        })
    else:
        sales_df = pd.DataFrame()

    # === F&B TRANSACTIONS (restaurants open year-round) ===
    fb_counts = np.array([int(rng.integers(*PERSONAS[p]['fb_trans'])) for p in personas])
    total_fb = int(fb_counts.sum())

    fb_df = pd.DataFrame({
        'TRANSACTION_ID': [f'FB{date_str}{i:08d}' for i in range(total_fb)],
        'CUSTOMER_ID': np.repeat(customer_ids, fb_counts),
        'LOCATION_ID': rng.choice(FB_LOCS, size=total_fb),
        'PRODUCT_ID': rng.choice(FB_PRODS, size=total_fb),
        'TRANSACTION_TIMESTAMP': [f'{visit_date} {rng.choice([10,11,12,13,14,15,16]):02d}:{int(rng.integers(0, 60)):02d}:00' for _ in range(total_fb)],
        'QUANTITY': rng.integers(1, 3, total_fb),
        'UNIT_PRICE': rng.integers(5, 18, total_fb).astype(float),
        'TOTAL_AMOUNT': rng.integers(5, 35, total_fb).astype(float),
        'PAYMENT_METHOD': rng.choice(['Credit Card', 'Debit Card', 'Cash'], size=total_fb),
        'CREATED_AT': created_at
    })

    # === RENTALS (bikes, helmets, hiking gear) ===
    rental_probs = np.array([PERSONAS[p]['rental_prob'] for p in personas])
    rental_mask = rng.random(n_visitors) < rental_probs
    n_rentals = rental_mask.sum()

    if n_rentals > 0:
        rental_items = rng.choice(SUMMER_RENTAL_ITEMS, size=n_rentals)
        rent_df = pd.DataFrame({
            'RENTAL_ID': [f'RENT{date_str}{i:06d}' for i in range(n_rentals)],
            'CUSTOMER_ID': customer_ids[rental_mask],
            'LOCATION_ID': rng.choice(RENTAL_LOCS, size=n_rentals),
            'PRODUCT_ID': [item['id'] for item in rental_items],
            'RENTAL_TIMESTAMP': f'{visit_date} 09:00:00',
            'RETURN_TIMESTAMP': f'{visit_date} 17:00:00',
            'RENTAL_DURATION_HOURS': 8.0,
            'RENTAL_AMOUNT': np.array([item['price'] for item in rental_items], dtype=float),
            'CREATED_AT': created_at
        })
    else:
        rent_df = pd.DataFrame()

    return scans_df, usage_df, sales_df, fb_df, rent_df


def generate_summer_lessons(date, n_visitors, daily_mod, customers_df):
    """Generate summer recreation lessons (mountain biking, guided hikes)."""
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    date_str = date.strftime('%Y-%m-%d')

    base_lessons = max(2, int(n_visitors * 0.06))
    if daily_mod['is_weekend']:
        base_lessons = int(base_lessons * 1.4)
    n_lessons = int(rng.integers(max(1, base_lessons - 2), base_lessons + 4))

    lesson_customers = customers_df.sample(n=min(n_lessons, len(customers_df)))['CUSTOMER_ID'].values

    records = []
    for i in range(n_lessons):
        lesson_type = rng.choice(SUMMER_LESSON_TYPES)
        start_hour = rng.choice([9, 10, 13, 14])

        if 'bike' in lesson_type:
            sport_type = 'mountain_bike'
            duration = 2
            if 'advanced' in lesson_type:
                group_size = int(rng.integers(3, 6))
                price = 120
            elif 'intermediate' in lesson_type:
                group_size = int(rng.integers(4, 8))
                price = 95
            else:
                group_size = int(rng.integers(4, 10))
                price = 85
        elif 'hike' in lesson_type:
            sport_type = 'hiking'
            duration = 3
            group_size = int(rng.integers(6, 15))
            price = 65
        else:
            sport_type = 'adventure'
            duration = 4
            group_size = int(rng.integers(6, 12))
            price = 110

        rental_included = rng.random() < 0.5

        records.append({
            'LESSON_ID': f'LESSON{date.strftime("%Y%m%d")}{i:04d}',
            'CUSTOMER_ID': lesson_customers[i % len(lesson_customers)],
            'LESSON_DATE': date_str,
            'LESSON_START_TIME': f'{start_hour:02d}:00:00',
            'LESSON_TYPE': lesson_type,
            'SPORT_TYPE': sport_type,
            'SKILL_LEVEL': rng.choice(['beginner', 'intermediate', 'advanced']),
            'DURATION_HOURS': float(duration),
            'INSTRUCTOR_ID': rng.choice(INSTRUCTOR_IDS),
            'GROUP_SIZE': group_size,
            'LESSON_AMOUNT': float(price),
            'RENTAL_INCLUDED': rental_included,
            'RENTAL_AMOUNT': float(35) if rental_included else 0.0,
            'TIP_AMOUNT': float(rng.choice([0, 10, 15, 20])),
            'BOOKING_CHANNEL': rng.choice(['online', 'phone', 'walk_in']),
            'BOOKING_LEAD_DAYS': int(rng.integers(0, 7)),
            'COMPLETED': True,
            'CANCELLATION_REASON': None,
            'STUDENT_RATING': float(rng.choice([4.0, 4.5, 5.0, 4.5, 5.0])) if rng.random() < 0.7 else None,
            'CREATED_AT': created_at
        })

    return pd.DataFrame(records)


def generate_summer_incidents(date, n_visitors, daily_mod, customers_df):
    """Generate summer safety incidents (bike crashes, trail falls, etc.)."""
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    date_str = date.strftime('%Y-%m-%d')

    incident_rate = 0.0015
    if daily_mod.get('is_rainy', False):
        incident_rate *= 1.4  # Wet trails increase incidents

    n_incidents = max(0, int(rng.poisson(n_visitors * incident_rate)))

    records = []
    for i in range(n_incidents):
        incident_type = rng.choice(SUMMER_INCIDENT_TYPES, p=[0.30, 0.30, 0.15, 0.05, 0.10, 0.10])
        severity = rng.choice(INCIDENT_SEVERITY, p=[0.72, 0.23, 0.05])
        hour = int(rng.integers(9, 17))
        minute = int(rng.integers(0, 60))

        trail_name = rng.choice(SUMMER_TRAIL_NAMES)
        lift_id = rng.choice(SUMMER_LIFT_IDS) if incident_type == 'equipment_failure' and rng.random() < 0.2 else None
        if lift_id:
            trail_name = None

        records.append({
            'INCIDENT_ID': f'INC{date.strftime("%Y%m%d")}{i:04d}',
            'INCIDENT_DATE': date_str,
            'INCIDENT_TIME': f'{hour:02d}:{minute:02d}:00',
            'INCIDENT_TIMESTAMP': f'{date_str} {hour:02d}:{minute:02d}:00',
            'INCIDENT_TYPE': incident_type,
            'SEVERITY': severity,
            'LOCATION_ID': f'LOC{int(rng.integers(1, 20)):03d}',
            'LIFT_ID': lift_id,
            'TRAIL_NAME': trail_name,
            'CUSTOMER_ID': rng.choice(customers_df['CUSTOMER_ID'].values) if rng.random() < 0.8 else None,
            'CUSTOMER_AGE': int(rng.integers(12, 65)) if rng.random() < 0.8 else None,
            'CUSTOMER_SKILL_LEVEL': rng.choice(['beginner', 'intermediate', 'advanced', 'expert']),
            'DESCRIPTION': f'{incident_type.replace("_", " ").title()} incident on {trail_name or "lift area"}',
            'CAUSE': rng.choice(['user_error', 'conditions', 'equipment', 'other']),
            'WEATHER_FACTOR': daily_mod.get('is_rainy', False),
            'EQUIPMENT_FACTOR': incident_type == 'equipment_failure',
            'FIRST_AID_RENDERED': severity in ['moderate', 'serious'],
            'TRANSPORT_REQUIRED': severity == 'serious',
            'TRANSPORT_TYPE': 'vehicle' if severity == 'serious' else None,
            'PATROL_RESPONSE_MINUTES': int(rng.integers(3, 12)),
            'RESOLUTION': 'resolved',
            'FOLLOWUP_REQUIRED': severity == 'serious',
            'REPORT_FILED': True,
            'CREATED_AT': created_at
        })

    return pd.DataFrame(records)


def generate_summer_feedback(date, n_visitors, daily_mod, customers_df):
    """Generate summer customer feedback."""
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    date_str = date.strftime('%Y-%m-%d')

    n_feedback = max(0, int(rng.poisson(n_visitors * 0.05)))
    if n_feedback == 0:
        return pd.DataFrame()

    summer_text_banks = {
        ('bike_park', 'pos'): [
            "Bike trails are well maintained. Flow track is so fun!",
            "Great variety of difficulty levels. Downhill run is world-class.",
            "Uplift service is fast and efficient. Got in 15 runs today.",
        ],
        ('bike_park', 'neg'): [
            "Some trails had big ruts that weren't marked. Sketchy.",
            "Bike park got too crowded on Saturday -- long uplift waits.",
            "Signage for trail difficulty is confusing. Nearly went off a drop.",
        ],
        ('trail_conditions', 'pos'): [
            "Wildflower Loop was stunning. Trails are in great shape.",
            "Well-marked trails with gorgeous views. Perfect day hike.",
            "Summit Trail is challenging but rewarding. Well maintained.",
        ],
        ('trail_conditions', 'neg'): [
            "Trails were muddy and poorly drained after yesterday's rain.",
            "Signage at the junction was missing -- got lost for 30 min.",
            "Overcrowded on the main loop. Needs capacity management.",
        ],
        ('food_service', 'pos'): [
            "Loved the summer BBQ menu at the lodge. Great beer selection.",
            "Patio dining with the mountain view is unbeatable.",
        ],
        ('food_service', 'neg'): [
            "Still overpriced for the quality. $18 for a mediocre burger.",
            "Ran out of water bottles by 2pm on a hot day. Come on.",
        ],
        ('events', 'pos'): [
            "Concert series is a great addition. Atmosphere was amazing.",
            "Family movie night on the lawn was a hit with the kids.",
        ],
        ('events', 'neg'): [
            "Concert sound quality was poor -- couldn't hear from the back.",
            "Event parking was a disaster. Took 40 min to leave.",
        ],
        ('overall_experience', 'pos'): [
            "Summer at Alpine Peaks is just as good as winter. We'll be back!",
            "Kids loved the adventure camp. Best summer activity in the area.",
            "Great value on the combo pass. Biking + gondola + lunch was perfect.",
        ],
        ('overall_experience', 'neg'): [
            "Not much to do if you don't mountain bike. Needs more activities.",
            "Expensive for what it is. Hiking trails should be free.",
        ],
    }

    visitor_ids = customers_df['CUSTOMER_ID'].values
    is_rainy = daily_mod.get('is_rainy', False)

    records = []
    for i in range(n_feedback):
        base_rating = 4.2 if not is_rainy else 3.6
        nps = int(min(10, max(0, rng.normal(base_rating * 2, 1.5))))
        satisfaction = round(min(5.0, max(1.0, rng.normal(base_rating, 0.7))), 1)

        if satisfaction >= 4:
            sentiment, bucket = 'positive', 'pos'
        elif satisfaction < 3:
            sentiment, bucket = 'negative', 'neg'
        else:
            sentiment, bucket = 'neutral', 'neu'

        category = rng.choice(SUMMER_FEEDBACK_CATEGORIES)
        subcategory = rng.choice(SUMMER_FEEDBACK_SUBCATEGORIES.get(category, ['general']))

        if rng.random() < 0.65:
            bank_key = (category, bucket)
            # Fall back to pos/neg if exact bucket isn't available
            bank = summer_text_banks.get(bank_key) or summer_text_banks.get((category, 'pos')) or ["Great summer experience."]
            feedback_text = str(rng.choice(bank))
        else:
            feedback_text = None

        has_response = rng.random() < 0.35
        response_text = "Thanks for the feedback! We'll share with the team." if has_response else None
        response_date = (date + timedelta(hours=float(rng.uniform(4, 48)))).strftime('%Y-%m-%d %H:%M:%S') if has_response else None
        responded_by = f'STAFF{int(rng.integers(1, 50)):03d}' if has_response else None
        resolved = bool(rng.random() < 0.7)

        records.append({
            'FEEDBACK_ID': f'FDBK{date.strftime("%Y%m%d")}{i:04d}',
            'CUSTOMER_ID': rng.choice(visitor_ids),
            'FEEDBACK_DATE': date_str,
            'FEEDBACK_TYPE': rng.choice(['survey', 'comment_card', 'email', 'app']),
            'SURVEY_ID': f'SURV{int(rng.integers(1, 100)):03d}',
            'NPS_SCORE': nps,
            'SATISFACTION_SCORE': satisfaction,
            'LIKELIHOOD_TO_RETURN': int(min(10, max(0, nps + int(rng.integers(-1, 2))))),
            'LIKELIHOOD_TO_RECOMMEND': nps,
            'CATEGORY': category,
            'SUBCATEGORY': subcategory,
            'SENTIMENT': sentiment,
            'SENTIMENT_SCORE': round(satisfaction / 5.0, 2),
            'FEEDBACK_TEXT': feedback_text,
            'RESPONSE_TEXT': response_text,
            'RESPONSE_DATE': response_date,
            'RESPONDED_BY': responded_by,
            'RESOLVED': resolved,
            'RESOLUTION_DATE': (date + timedelta(hours=float(rng.uniform(24, 120)))).strftime('%Y-%m-%d %H:%M:%S') if resolved else None,
            'ESCALATED': bool(satisfaction < 2.5),
            'SOURCE': rng.choice(['email', 'app', 'kiosk', 'web']),
            'VISIT_DATE': date_str,
            'CREATED_AT': created_at,
        })

    return pd.DataFrame(records)


def generate_summer_maintenance(date, daily_mod):
    """Generate summer lift/trail maintenance logs."""
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    date_str = date.strftime('%Y-%m-%d')

    records = []
    # Only summer-operating lifts get maintenance
    for lift_id in SUMMER_LIFT_IDS:
        if rng.random() < 0.12:
            maint_type = rng.choice(['repair', 'replacement', 'adjustment'])
            downtime = int(rng.integers(20, 120))
            during_ops = rng.random() < 0.2
            parts_cost = float(rng.integers(100, 1500)) if maint_type == 'replacement' else 0.0
        else:
            maint_type = 'inspection'
            downtime = 0
            during_ops = False
            parts_cost = 0.0

        labor_hours = round(rng.uniform(0.5, 2.5), 1)
        labor_cost = float(labor_hours * 75)

        records.append({
            'MAINTENANCE_ID': f'MAINT{date.strftime("%Y%m%d")}{lift_id}',
            'LIFT_ID': lift_id,
            'MAINTENANCE_DATE': date_str,
            'MAINTENANCE_TYPE': maint_type,
            'CATEGORY': rng.choice(['mechanical', 'electrical', 'safety', 'routine']),
            'DESCRIPTION': f'Summer {maint_type} for {lift_id}',
            'START_TIME': f'{date_str} 06:00:00',
            'END_TIME': f'{date_str} 07:30:00',
            'DOWNTIME_MINUTES': downtime,
            'DURING_OPERATING_HOURS': during_ops,
            'PARTS_REPLACED': maint_type == 'replacement',
            'PARTS_COST': parts_cost,
            'LABOR_HOURS': labor_hours,
            'LABOR_COST': labor_cost,
            'TOTAL_COST': parts_cost + labor_cost,
            'TECHNICIAN_ID': f'TECH{int(rng.integers(1, 10)):03d}',
            'PASSED_INSPECTION': maint_type == 'inspection' or rng.random() < 0.95,
            'FOLLOWUP_REQUIRED': maint_type != 'inspection' and rng.random() < 0.1,
            'NOTES': f'Summer {maint_type.title()} completed' if rng.random() < 0.3 else None,
            'CREATED_AT': created_at
        })

    return pd.DataFrame(records)


def generate_summer_grooming(date, daily_mod):
    """Generate summer trail maintenance/grooming logs."""
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    date_str = date.strftime('%Y-%m-%d')

    # Fewer trails groomed in summer, early morning work
    n_trails = min(len(SUMMER_TRAIL_NAMES), int(round(rng.normal(6, 2))))
    n_trails = max(3, n_trails)
    trails_maintained = list(rng.choice(SUMMER_TRAIL_NAMES, size=n_trails, replace=False))

    records = []
    for i, trail in enumerate(trails_maintained):
        start_hour = int(rng.integers(5, 8))
        end_hour = start_hour + int(rng.integers(1, 3))
        duration = (end_hour - start_hour) * 60 + int(rng.integers(-10, 20))

        records.append({
            'LOG_ID': f'GROOM{date.strftime("%Y%m%d")}{i:03d}',
            'GROOMING_DATE': date_str,
            'SHIFT': 'morning',
            'TRAIL_NAME': trail,
            'GROOMER_ID': f'EMP{int(rng.integers(50, 60)):03d}',
            'MACHINE_ID': f'CAT{int(rng.integers(1, 4)):02d}',
            'START_TIME': f'{date_str} {start_hour:02d}:00:00',
            'END_TIME': f'{date_str} {end_hour:02d}:00:00',
            'DURATION_MINUTES': duration,
            'GROOMING_TYPE': rng.choice(['trail_repair', 'brush_clearing', 'drainage_work']),
            'SNOW_DEPTH_INCHES': 0.0,
            'CONDITIONS_BEFORE': rng.choice(['good', 'fair', 'muddy', 'eroded']),
            'CONDITIONS_AFTER': rng.choice(['excellent', 'good', 'fair']),
            'FUEL_USED_GALLONS': round(rng.uniform(3, 12), 1),
            'NOTES': f'Trail maintenance on {trail}' if rng.random() < 0.3 else None,
            'CREATED_AT': created_at
        })

    return pd.DataFrame(records)


def main():
    parser = argparse.ArgumentParser(description="Generate incremental daily data - ALL data types.")
    parser.add_argument('--date', type=str, default=datetime.now().strftime('%Y-%m-%d'),
                        help='Start date (YYYY-MM-DD). Defaults to today.')
    parser.add_argument('--days', type=int, default=1, help='Number of days (default: 1)')
    parser.add_argument('--connection', type=str, default='snowflake_agents', help='Snow CLI connection')
    parser.add_argument('--force', action='store_true', help='Force regeneration even if data exists')
    parser.add_argument('--env', type=str, default='prod', choices=VALID_ENVS,
                        help=f'Target environment (default: prod). Valid: {VALID_ENVS}')
    args = parser.parse_args()

    target_db = get_database_for_env(args.env) if args.env != 'prod' else DATABASE
    start_date = datetime.strptime(args.date, '%Y-%m-%d')

    logger.info("=" * 60)
    logger.info("INCREMENTAL DATA GENERATION - ALL DATA TYPES")
    logger.info("=" * 60)
    logger.info(f"Environment: {args.env} -> Database: {target_db}")
    logger.info(f"Generating {args.days} day(s) starting {start_date.strftime('%Y-%m-%d')}")

    try:
        conn = SnowflakeConnection.from_env_or_snow_cli(args.connection)
    except Exception as e:
        logger.info(f"Using Snow CLI connection '{args.connection}'")
        conn = SnowflakeConnection.from_snow_cli(args.connection)

    conn.execute(f"USE DATABASE {target_db}")
    conn.execute(f"USE SCHEMA {RAW_SCHEMA}")

    # Load customers
    customers_df = conn.sql("SELECT CUSTOMER_ID, CUSTOMER_SEGMENT, IS_PASS_HOLDER FROM CUSTOMERS").to_pandas()
    logger.info(f"Loaded {len(customers_df)} customers")

    # Collect all data
    all_weather, all_staffing = [], []
    all_scans, all_usage, all_sales, all_fb, all_rentals = [], [], [], [], []
    all_lessons, all_incidents, all_feedback = [], [], []
    all_parking, all_maintenance, all_grooming = [], [], []

    skipped_dates = []
    fully_skipped = []

    for day_offset in range(args.days):
        current_date = start_date + timedelta(days=day_offset)
        date_str = current_date.strftime('%Y-%m-%d')

        # === Per-table idempotency ===
        # Skip only the tables that already have rows for this date; let the
        # rest fill in. --force overrides everything (treats every table as
        # absent so it gets re-generated).
        if args.force:
            present = {tag: False for tag in IDEMPOTENCY_TABLES}
        else:
            present = present_for_date(conn, current_date)
        if all(present.values()):
            fully_skipped.append(date_str)
            continue
        missing = [t for t, p in present.items() if not p]
        if len(missing) < len(IDEMPOTENCY_TABLES):
            logger.info(
                "  %s: backfilling %d missing table(s): %s",
                date_str, len(missing), ", ".join(sorted(missing)),
            )
        skipped_dates.append((date_str, missing))

        daily_mod = get_daily_modifier(current_date, rng)

        # Year-round generation -- skip if already present for this date.
        if not present["WEATHER_CONDITIONS"]:
            all_weather.append(generate_weather(current_date, daily_mod))
        if not present["STAFFING_SCHEDULE"]:
            all_staffing.append(generate_staffing(current_date, daily_mod))

        # Season-gated generation -- gated by season AND per-table presence.
        # Now supports both winter (Nov-Apr) and summer (May-Oct) operations.
        is_summer = daily_mod.get('is_summer', False)

        if daily_mod['season_mult'] > 0:
            if not present["LIFT_MAINTENANCE"]:
                if is_summer:
                    all_maintenance.append(generate_summer_maintenance(current_date, daily_mod))
                else:
                    all_maintenance.append(generate_lift_maintenance(current_date, daily_mod))
            if not present["GROOMING_LOGS"]:
                if is_summer:
                    all_grooming.append(generate_summer_grooming(current_date, daily_mod))
                else:
                    all_grooming.append(generate_grooming_logs(current_date, daily_mod))

            # Transactional bundle: only call the transaction generator if any
            # of its outputs are missing.
            transactional_missing = any(
                not present[t] for t in (
                    "LIFT_SCANS", "PASS_USAGE", "TICKET_SALES",
                    "FOOD_BEVERAGE", "RENTALS",
                )
            )
            extras_missing = any(
                not present[t] for t in (
                    "SKI_LESSONS", "INCIDENTS", "CUSTOMER_FEEDBACK",
                    "PARKING_OCCUPANCY",
                )
            )
            if transactional_missing or extras_missing:
                if is_summer:
                    result = generate_summer_transactions(current_date, customers_df, daily_mod)
                else:
                    result = generate_day_transactions(current_date, customers_df, daily_mod)

                if result[0] is not None:
                    n_visitors = len(result[1])
                    if not present["LIFT_SCANS"]:
                        all_scans.append(result[0])
                    if not present["PASS_USAGE"]:
                        all_usage.append(result[1])
                    if not present["TICKET_SALES"] and not result[2].empty:
                        all_sales.append(result[2])
                    if not present["FOOD_BEVERAGE"]:
                        all_fb.append(result[3])
                    if not present["RENTALS"] and not result[4].empty:
                        all_rentals.append(result[4])

                    if not present["SKI_LESSONS"]:
                        if is_summer:
                            all_lessons.append(generate_summer_lessons(current_date, n_visitors, daily_mod, customers_df))
                        else:
                            all_lessons.append(generate_ski_lessons(current_date, n_visitors, daily_mod, customers_df))
                    if not present["INCIDENTS"]:
                        if is_summer:
                            all_incidents.append(generate_summer_incidents(current_date, n_visitors, daily_mod, customers_df))
                        else:
                            all_incidents.append(generate_incidents(current_date, n_visitors, daily_mod, customers_df))
                    if not present["CUSTOMER_FEEDBACK"]:
                        if is_summer:
                            all_feedback.append(generate_summer_feedback(current_date, n_visitors, daily_mod, customers_df))
                        else:
                            all_feedback.append(generate_customer_feedback(current_date, n_visitors, daily_mod, customers_df))
                    if not present["PARKING_OCCUPANCY"]:
                        all_parking.append(generate_parking_occupancy(current_date, n_visitors, daily_mod))

    if fully_skipped:
        logger.info(
            "\n⏭️  Skipped %d date(s) with full coverage: %s",
            len(fully_skipped),
            ", ".join(fully_skipped[:5]) + ("..." if len(fully_skipped) > 5 else ""),
        )

    # If absolutely nothing was collected for any table, exit early. This
    # is the per-table-aware version of the old `if not all_weather` check
    # -- with per-table idempotency, weather may already be present while
    # other tables (e.g. CUSTOMER_FEEDBACK after the SUBCATEGORY bug)
    # are still missing for the same dates.
    all_collections = (
        all_weather, all_staffing, all_scans, all_usage, all_sales,
        all_fb, all_rentals, all_lessons, all_incidents, all_feedback,
        all_parking, all_maintenance, all_grooming,
    )
    if not any(all_collections):
        logger.info("\n✅ No new data to generate (every requested table already has rows for these dates)")
        conn.close()
        return

    # Combine DataFrames -- only when their list has entries. The original
    # code unconditionally concat()'d weather/staffing which crashes on
    # an empty list when the per-table idempotency leaves them untouched.
    weather_df = pd.concat(all_weather, ignore_index=True) if all_weather else pd.DataFrame()
    staffing_df = pd.concat(all_staffing, ignore_index=True) if all_staffing else pd.DataFrame()

    logger.info(f"\n📊 Generated Data (Original Tables):")
    logger.info(f"  Weather:       {len(weather_df):,}")
    logger.info(f"  Staffing:      {len(staffing_df):,}")

    if all_scans:
        scans_df = pd.concat(all_scans, ignore_index=True)
        usage_df = pd.concat(all_usage, ignore_index=True) if all_usage else pd.DataFrame()
        sales_df = pd.concat(all_sales, ignore_index=True) if all_sales else pd.DataFrame()
        fb_df = pd.concat(all_fb, ignore_index=True) if all_fb else pd.DataFrame()
        rentals_df = pd.concat(all_rentals, ignore_index=True) if all_rentals else pd.DataFrame()

        logger.info(f"  Lift scans:    {len(scans_df):,}")
        logger.info(f"  Pass usage:    {len(usage_df):,}")
        logger.info(f"  Ticket sales:  {len(sales_df):,}")
        logger.info(f"  F&B trans:     {len(fb_df):,}")
        logger.info(f"  Rentals:       {len(rentals_df):,}")
    else:
        scans_df = pd.DataFrame()
        usage_df = pd.DataFrame()
        sales_df = pd.DataFrame()
        fb_df = pd.DataFrame()
        rentals_df = pd.DataFrame()

    logger.info(f"\n📊 Generated Data (New Tables):")

    lessons_df = pd.concat(all_lessons, ignore_index=True) if all_lessons else pd.DataFrame()
    incidents_df = pd.concat(all_incidents, ignore_index=True) if all_incidents else pd.DataFrame()
    feedback_df = pd.concat(all_feedback, ignore_index=True) if all_feedback else pd.DataFrame()
    parking_df = pd.concat(all_parking, ignore_index=True) if all_parking else pd.DataFrame()
    maintenance_df = pd.concat(all_maintenance, ignore_index=True) if all_maintenance else pd.DataFrame()
    grooming_df = pd.concat(all_grooming, ignore_index=True) if all_grooming else pd.DataFrame()

    logger.info(f"  Ski lessons:   {len(lessons_df):,}")
    logger.info(f"  Incidents:     {len(incidents_df):,}")
    logger.info(f"  Feedback:      {len(feedback_df):,}")
    logger.info(f"  Parking:       {len(parking_df):,}")
    logger.info(f"  Maintenance:   {len(maintenance_df):,}")
    logger.info(f"  Grooming:      {len(grooming_df):,}")

    logger.info("\n📤 Loading to Snowflake...")

    # Per-table writes -- only call write_pandas when the corresponding
    # DataFrame has rows. Avoids writing an empty DataFrame which fails
    # on auto_create_table=False.
    if not weather_df.empty:
        conn.session.write_pandas(weather_df, table_name="WEATHER_CONDITIONS", auto_create_table=False, overwrite=False)
    if not staffing_df.empty:
        conn.session.write_pandas(staffing_df, table_name="STAFFING_SCHEDULE", auto_create_table=False, overwrite=False)

    if not scans_df.empty:
        conn.session.write_pandas(scans_df, table_name="LIFT_SCANS", auto_create_table=False, overwrite=False)
    if not usage_df.empty:
        conn.session.write_pandas(usage_df, table_name="PASS_USAGE", auto_create_table=False, overwrite=False)
    if not sales_df.empty:
        conn.session.write_pandas(sales_df, table_name="TICKET_SALES", auto_create_table=False, overwrite=False)
    if not fb_df.empty:
        conn.session.write_pandas(fb_df, table_name="FOOD_BEVERAGE", auto_create_table=False, overwrite=False)
    if not rentals_df.empty:
        conn.session.write_pandas(rentals_df, table_name="RENTALS", auto_create_table=False, overwrite=False)

    # Load NEW tables
    if not lessons_df.empty:
        conn.session.write_pandas(lessons_df, table_name="SKI_LESSONS", auto_create_table=False, overwrite=False)
    if not incidents_df.empty:
        conn.session.write_pandas(incidents_df, table_name="INCIDENTS", auto_create_table=False, overwrite=False)
    if not feedback_df.empty:
        conn.session.write_pandas(feedback_df, table_name="CUSTOMER_FEEDBACK", auto_create_table=False, overwrite=False)
    if not parking_df.empty:
        conn.session.write_pandas(parking_df, table_name="PARKING_OCCUPANCY", auto_create_table=False, overwrite=False)
    if not maintenance_df.empty:
        conn.session.write_pandas(maintenance_df, table_name="LIFT_MAINTENANCE", auto_create_table=False, overwrite=False)
    if not grooming_df.empty:
        conn.session.write_pandas(grooming_df, table_name="GROOMING_LOGS", auto_create_table=False, overwrite=False)

    logger.info("✅ Incremental load complete!")
    conn.close()


if __name__ == "__main__":
    main()
