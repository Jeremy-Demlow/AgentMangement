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
from config import DATABASE, RAW_SCHEMA

# Import shared constants and utilities
from shared import (
    get_rng, get_daily_modifier, get_snow_condition, calculate_wait_time,
    PERSONAS, LIFT_IDS, LIFT_CAPACITY, LIFT_POPULARITY,
    RENTAL_LOCS, FB_LOCS, RENTAL_PRODS, FB_PRODS, DAY_PASSES, TICKET_PRICES,
    WEATHER_ZONES, STAFFING_DEPARTMENTS, INSTRUCTOR_IDS, PARKING_LOT_INFO,
    TRAIL_NAMES, LESSON_TYPES, INCIDENT_TYPES, INCIDENT_SEVERITY
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Use unseeded RNG for incremental (truly random daily data)
rng = get_rng()


# =============================================================================
# IDEMPOTENCY CHECK
# =============================================================================
def check_date_exists(conn, table_name, date_column, date_value):
    """Check if data for a specific date already exists in a table."""
    query = f"""
        SELECT COUNT(*) as cnt
        FROM {DATABASE}.{RAW_SCHEMA}.{table_name}
        WHERE {date_column} = '{date_value}'
    """
    result = conn.sql(query).to_pandas()
    return result['CNT'].iloc[0] > 0


def check_any_data_exists(conn, date):
    """Check if any data exists for the given date."""
    date_str = date.strftime('%Y-%m-%d')

    checks = [
        ('WEATHER_CONDITIONS', 'WEATHER_DATE'),
        ('PASS_USAGE', 'VISIT_DATE'),
        ('LIFT_SCANS', "SCAN_TIMESTAMP::DATE"),
    ]

    for table, col in checks:
        if check_date_exists(conn, table, col, date_str):
            return True
    return False


# =============================================================================
# DATA GENERATION FUNCTIONS
# =============================================================================
def generate_weather(date, daily_mod):
    """Generate weather records for all zones."""
    records = []
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for zone in WEATHER_ZONES:
        snowfall = max(0.0, daily_mod['snowfall'] + rng.normal(0, 1.0))
        base_depth = max(18.0, 36 + rng.normal(0, 5.0))
        temp_high = daily_mod['temp_high_f'] + int(rng.integers(-3, 4))
        temp_low = daily_mod['temp_low_f'] + int(rng.integers(-3, 4))
        wind_speed = int(rng.integers(3, 25))

        snow_condition = get_snow_condition(snowfall, date.month)

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
    """Generate staffing records for the day."""
    entries = []
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    is_weekend = daily_mod['is_weekend']

    for dept in STAFFING_DEPARTMENTS:
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
    """Generate customer feedback/surveys."""
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    date_str = date.strftime('%Y-%m-%d')

    n_feedback = max(0, int(rng.poisson(n_visitors * 0.05)))

    records = []
    for i in range(n_feedback):
        base_rating = 4.0
        if daily_mod['is_powder_day']:
            base_rating += 0.3
        if daily_mod['storm_warning']:
            base_rating -= 0.5

        nps = int(min(10, max(0, rng.normal(base_rating * 2, 1.5))))
        satisfaction = round(min(5.0, max(1.0, rng.normal(base_rating, 0.7))), 1)
        sentiment = 'positive' if satisfaction >= 4 else ('negative' if satisfaction < 3 else 'neutral')

        records.append({
            'FEEDBACK_ID': f'FDBK{date.strftime("%Y%m%d")}{i:04d}',
            'CUSTOMER_ID': rng.choice(customers_df['CUSTOMER_ID'].values),
            'FEEDBACK_DATE': date_str,
            'FEEDBACK_TYPE': rng.choice(['survey', 'comment_card', 'email', 'app']),
            'SURVEY_ID': f'SURV{int(rng.integers(1, 100)):03d}',
            'NPS_SCORE': nps,
            'SATISFACTION_SCORE': satisfaction,
            'LIKELIHOOD_TO_RETURN': int(min(10, max(0, nps + int(rng.integers(-1, 2))))),
            'LIKELIHOOD_TO_RECOMMEND': nps,
            'CATEGORY': rng.choice(['lift_operations', 'food_service', 'rental_shop',
                                    'ski_school', 'facilities', 'overall_experience']),
            'SUBCATEGORY': rng.choice(['speed', 'cleanliness', 'staff', 'value', 'quality']),
            'SENTIMENT': sentiment,
            'SENTIMENT_SCORE': round(satisfaction / 5.0, 2),
            'FEEDBACK_TEXT': f'Sample feedback for {date_str}' if rng.random() < 0.3 else None,
            'RESPONSE_TEXT': 'Thank you for your feedback!' if rng.random() < 0.2 else None,
            'RESPONSE_DATE': date_str if rng.random() < 0.2 else None,
            'RESPONDED_BY': f'STAFF{int(rng.integers(1, 50)):03d}' if rng.random() < 0.2 else None,
            'RESOLVED': rng.random() < 0.9,
            'RESOLUTION_DATE': date_str if rng.random() < 0.8 else None,
            'ESCALATED': satisfaction < 2.5,
            'SOURCE': rng.choice(['email', 'app', 'kiosk', 'web']),
            'VISIT_DATE': date_str,
            'CREATED_AT': created_at
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


def main():
    parser = argparse.ArgumentParser(description="Generate incremental daily data - ALL data types.")
    parser.add_argument('--date', type=str, default=datetime.now().strftime('%Y-%m-%d'),
                        help='Start date (YYYY-MM-DD). Defaults to today.')
    parser.add_argument('--days', type=int, default=1, help='Number of days (default: 1)')
    parser.add_argument('--connection', type=str, default='snowflake_agents', help='Snow CLI connection')
    parser.add_argument('--force', action='store_true', help='Force regeneration even if data exists')
    args = parser.parse_args()

    start_date = datetime.strptime(args.date, '%Y-%m-%d')

    logger.info("=" * 60)
    logger.info("INCREMENTAL DATA GENERATION - ALL DATA TYPES")
    logger.info("=" * 60)
    logger.info(f"Generating {args.days} day(s) starting {start_date.strftime('%Y-%m-%d')}")

    # Try environment variables first (for CI/CD), then fall back to Snow CLI
    try:
        conn = SnowflakeConnection.from_env_or_snow_cli(args.connection)
    except Exception as e:
        logger.info(f"Using Snow CLI connection '{args.connection}'")
        conn = SnowflakeConnection.from_snow_cli(args.connection)

    conn.execute(f"USE DATABASE {DATABASE}")
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

    for day_offset in range(args.days):
        current_date = start_date + timedelta(days=day_offset)
        date_str = current_date.strftime('%Y-%m-%d')

        # === IDEMPOTENCY CHECK ===
        if not args.force and check_any_data_exists(conn, current_date):
            logger.warning(f"⚠️  Data for {date_str} already exists, skipping (use --force to override)")
            skipped_dates.append(date_str)
            continue

        daily_mod = get_daily_modifier(current_date, rng)

        # Generate weather and staffing (always)
        all_weather.append(generate_weather(current_date, daily_mod))
        all_staffing.append(generate_staffing(current_date, daily_mod))

        # Generate lift maintenance and grooming (always during season)
        if daily_mod['season_mult'] > 0:
            all_maintenance.append(generate_lift_maintenance(current_date, daily_mod))
            all_grooming.append(generate_grooming_logs(current_date, daily_mod))

        # Generate visitor-based data (only ski season)
        if daily_mod['season_mult'] > 0:
            result = generate_day_transactions(current_date, customers_df, daily_mod)
            if result[0] is not None:
                n_visitors = len(result[1])

                all_scans.append(result[0])
                all_usage.append(result[1])
                if not result[2].empty:
                    all_sales.append(result[2])
                all_fb.append(result[3])
                if not result[4].empty:
                    all_rentals.append(result[4])

                # Generate additional daily data
                all_lessons.append(generate_ski_lessons(current_date, n_visitors, daily_mod, customers_df))
                all_incidents.append(generate_incidents(current_date, n_visitors, daily_mod, customers_df))
                all_feedback.append(generate_customer_feedback(current_date, n_visitors, daily_mod, customers_df))
                all_parking.append(generate_parking_occupancy(current_date, n_visitors, daily_mod))

    if skipped_dates:
        logger.info(f"\n⏭️  Skipped {len(skipped_dates)} date(s) with existing data: {', '.join(skipped_dates)}")

    if not all_weather:
        logger.info("\n✅ No new data to generate (all dates already exist)")
        conn.close()
        return

    # Combine DataFrames
    weather_df = pd.concat(all_weather, ignore_index=True)
    staffing_df = pd.concat(all_staffing, ignore_index=True)

    logger.info(f"\n📊 Generated Data (Original Tables):")
    logger.info(f"  Weather:       {len(weather_df):,}")
    logger.info(f"  Staffing:      {len(staffing_df):,}")

    if all_scans:
        scans_df = pd.concat(all_scans, ignore_index=True)
        usage_df = pd.concat(all_usage, ignore_index=True)
        sales_df = pd.concat(all_sales, ignore_index=True) if all_sales else pd.DataFrame()
        fb_df = pd.concat(all_fb, ignore_index=True)
        rentals_df = pd.concat(all_rentals, ignore_index=True) if all_rentals else pd.DataFrame()

        logger.info(f"  Lift scans:    {len(scans_df):,}")
        logger.info(f"  Pass usage:    {len(usage_df):,}")
        logger.info(f"  Ticket sales:  {len(sales_df):,}")
        logger.info(f"  F&B trans:     {len(fb_df):,}")
        logger.info(f"  Rentals:       {len(rentals_df):,}")

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

    # Load all tables (append mode)
    conn.session.write_pandas(weather_df, table_name="WEATHER_CONDITIONS", auto_create_table=False, overwrite=False)
    conn.session.write_pandas(staffing_df, table_name="STAFFING_SCHEDULE", auto_create_table=False, overwrite=False)

    if all_scans:
        conn.session.write_pandas(scans_df, table_name="LIFT_SCANS", auto_create_table=False, overwrite=False)
        conn.session.write_pandas(usage_df, table_name="PASS_USAGE", auto_create_table=False, overwrite=False)
        if not sales_df.empty:
            conn.session.write_pandas(sales_df, table_name="TICKET_SALES", auto_create_table=False, overwrite=False)
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
