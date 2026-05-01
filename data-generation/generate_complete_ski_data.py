"""
Optimized Complete Ski Resort Data Generation
Vectorized operations for 10-20x performance improvement
Generates ALL operational data with proper Snowflake date handling
"""

import argparse
from pathlib import Path
import time
import pandas as pd
import numpy as np
from faker import Faker
from datetime import datetime, timedelta
import logging
from snowflake_connection import SnowflakeConnection
from config import DATABASE, RAW_SCHEMA
from tqdm import tqdm

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize single random generator for reproducibility
rng = np.random.default_rng(42)
fake = Faker()
Faker.seed(42)

# Date range defaults (can be overridden via CLI)
# Generate 5 full ski seasons: Nov 2020 through current date
START_DATE = datetime(2020, 11, 1)
END_DATE = datetime.now()  # Generate up to today!


def parse_args():
    parser = argparse.ArgumentParser(description="Generate synthetic ski resort operational data.")
    parser.add_argument('--start-date', type=lambda s: datetime.strptime(s, '%Y-%m-%d'),
                        help='Inclusive start date (YYYY-MM-DD). Defaults to 2020-11-01.')
    parser.add_argument('--end-date', type=lambda s: datetime.strptime(s, '%Y-%m-%d'),
                        help='Inclusive end date (YYYY-MM-DD). Defaults to 2024-04-30.')
    parser.add_argument('--export-only', action='store_true',
                        help='Export generated tables to compressed CSV files instead of loading into Snowflake.')
    parser.add_argument('--save-local', action='store_true',
                        help='Save generated data locally (CSV.gz) in addition to loading to Snowflake.')
    parser.add_argument('--export-dir', type=str, default='../ski_resort_data',
                        help='Directory to write exported CSV files (default: ../ski_resort_data).')
    parser.add_argument('--progress-interval', type=int, default=30,
                        help='Log generation progress every N days (default: 30).')
    return parser.parse_args()

# Customer Persona Distribution (8,000 total customers)
PERSONAS = {
    'local_pass_holder': {
        'count': 1200,
        'base_prob': {'weekday': 0.12, 'weekend': 0.08},
        'laps_range': (15, 25),
        'rental_prob': 0.05,
        'fb_trans': (1, 3)
    },
    'weekend_warrior': {
        'count': 2000,
        'base_prob': {'weekday': 0.02, 'saturday': 0.15, 'sunday': 0.08},
        'laps_range': (10, 15),
        'rental_prob': 0.15,
        'fb_trans': (2, 4)
    },
    'vacation_family': {
        'count': 2400,
        'base_prob': {'weekday': 0.025, 'weekend': 0.035},
        'laps_range': (6, 10),
        'rental_prob': 0.85,
        'fb_trans': (3, 6)
    },
    'day_tripper': {
        'count': 1600,
        'base_prob': {'weekday': 0.005, 'weekend': 0.015},
        'laps_range': (8, 12),
        'rental_prob': 0.45,
        'fb_trans': (1, 2)
    },
    'expert_skier': {
        'count': 400,
        'base_prob': {'weekday': 0.12, 'weekend': 0.12},
        'laps_range': (18, 28),
        'rental_prob': 0.20,
        'fb_trans': (0, 2)
    },
    'group_corporate': {
        'count': 240,
        'base_prob': {'weekday': 0.008, 'weekend': 0.002},
        'laps_range': (5, 10),
        'rental_prob': 0.70,
        'fb_trans': (3, 5)
    },
    'beginner': {
        'count': 160,
        'base_prob': {'weekday': 0.01, 'weekend': 0.01},
        'laps_range': (4, 7),
        'rental_prob': 0.95,
        'fb_trans': (2, 4)
    }
}

# Lift IDs for vectorized selection
LIFT_IDS = [f'L{str(i+1).zfill(3)}' for i in range(18)]

# Lift capacity per hour (from DIM_LIFT) - realistic operational data
LIFT_CAPACITY = {
    'L001': 2500,  # Summit Express Gondola - highest capacity
    'L002': 1500,  # Eagle Ridge 6-pack
    'L003': 1200,  # Blue Sky 4-pack
    'L004': 1200,  # Family Fun 4-pack
    'L005': 1000,  # Black Diamond chair
    'L006': 1200,  # Sunshine 4-pack
    'L007': 800,   # Backbowl Access
    'L008': 800,   # North Face
    'L009': 1000,  # Terrain Park Express
    'L010': 1200,  # Mid Mountain 4-pack
    'L011': 600,   # Expert Chutes
    'L012': 800,   # Powder Bowl
    'L013': 1200,  # East Side 4-pack
    'L014': 1200,  # South Ridge 4-pack
    'L015': 800,   # Magic Carpet (beginner)
    'L016': 600,   # Learning Area
    'L017': 1500,  # Cruiser 6-pack
    'L018': 400,   # Backcountry Gate
}

# Lift popularity weights (higher = more people choose this lift)
LIFT_POPULARITY = {
    'L001': 1.8,   # Summit gondola - most popular
    'L002': 1.3,   # Eagle Ridge
    'L003': 1.2,   # Blue Sky
    'L004': 1.4,   # Family Fun - popular with families
    'L005': 0.7,   # Black Diamond - fewer experts
    'L006': 1.1,   # Sunshine
    'L007': 0.5,   # Backbowl - remote
    'L008': 0.6,   # North Face
    'L009': 0.9,   # Terrain Park
    'L010': 1.5,   # Mid Mountain - central location
    'L011': 0.3,   # Expert Chutes - very few
    'L012': 0.6,   # Powder Bowl
    'L013': 1.0,   # East Side
    'L014': 1.1,   # South Ridge
    'L015': 0.8,   # Magic Carpet
    'L016': 0.5,   # Learning Area
    'L017': 1.4,   # Cruiser - popular intermediate
    'L018': 0.2,   # Backcountry Gate - very few
}

# Product/location mappings
RENTAL_LOCS = ['LOC001', 'LOC002', 'LOC003', 'LOC004', 'LOC005', 'LOC006']
FB_LOCS = ['LOC007', 'LOC008', 'LOC009', 'LOC010', 'LOC011', 'LOC012', 'LOC013', 'LOC014', 'LOC015', 'LOC016']
TICKET_LOCS = ['LOC017', 'LOC018', 'LOC019', 'LOC020', 'LOC021']

RENTAL_PRODS = [f'PROD{str(i).zfill(3)}' for i in range(1, 14)]
FOOD_PRODS = [f'PROD{str(i).zfill(3)}' for i in range(14, 22)]
BEV_PRODS = [f'PROD{str(i).zfill(3)}' for i in range(22, 32)]

SEASON_PASSES = ['TKT008', 'TKT009', 'TKT010', 'TKT011', 'TKT012', 'TKT013', 'TKT014', 'TKT018']
DAY_PASSES = ['TKT001', 'TKT002', 'TKT003', 'TKT004', 'TKT015', 'TKT016']
MULTI_DAY = ['TKT005', 'TKT006', 'TKT007']

WEATHER_ZONES = ['Summit Peak', 'North Ridge', 'Alpine Bowl', 'Village Base']

# ============================================================================
# PHASE 1-3: NEW REFERENCE DATA
# ============================================================================

# Parking lots
PARKING_LOTS = [
    {'lot_id': 'PKG001', 'lot_name': 'Main Lot', 'lot_type': 'Main', 'total_spaces': 1200, 'hourly_rate': 0, 'daily_max': 25, 'distance_to_lifts_feet': 200, 'has_shuttle': False, 'elevation_zone': 'Base'},
    {'lot_id': 'PKG002', 'lot_name': 'Village Lot', 'lot_type': 'Main', 'total_spaces': 800, 'hourly_rate': 0, 'daily_max': 30, 'distance_to_lifts_feet': 100, 'has_shuttle': False, 'elevation_zone': 'Base'},
    {'lot_id': 'PKG003', 'lot_name': 'Overflow East', 'lot_type': 'Overflow', 'total_spaces': 600, 'hourly_rate': 0, 'daily_max': 15, 'distance_to_lifts_feet': 800, 'has_shuttle': True, 'elevation_zone': 'Base'},
    {'lot_id': 'PKG004', 'lot_name': 'Overflow West', 'lot_type': 'Overflow', 'total_spaces': 500, 'hourly_rate': 0, 'daily_max': 15, 'distance_to_lifts_feet': 1000, 'has_shuttle': True, 'elevation_zone': 'Base'},
    {'lot_id': 'PKG005', 'lot_name': 'VIP Lot', 'lot_type': 'VIP', 'total_spaces': 50, 'hourly_rate': 0, 'daily_max': 75, 'distance_to_lifts_feet': 50, 'has_shuttle': False, 'elevation_zone': 'Base'},
    {'lot_id': 'PKG006', 'lot_name': 'Employee Lot', 'lot_type': 'Employee', 'total_spaces': 200, 'hourly_rate': 0, 'daily_max': 0, 'distance_to_lifts_feet': 400, 'has_shuttle': False, 'elevation_zone': 'Base'},
]

# Instructors
INSTRUCTOR_LEVELS = ['Level_1', 'Level_2', 'Level_3', 'Examiner']
INSTRUCTOR_SPECIALTIES = ['Kids', 'Racing', 'Freestyle', 'Adaptive', 'Adult_Beginner', 'Advanced_Technique']
LESSON_TYPES = ['Private', 'Semi_Private', 'Group', 'Kids_Camp', 'Race_Clinic', 'Freestyle_Camp']
SKILL_LEVELS = ['First_Timer', 'Beginner', 'Intermediate', 'Advanced', 'Expert']

# Incident types
INCIDENT_TYPES = ['Injury', 'Equipment_Failure', 'Weather_Closure', 'Lift_Stop', 'Lost_Skier', 'Collision', 'Medical_Emergency']
INCIDENT_SEVERITIES = ['Minor', 'Moderate', 'Major', 'Critical']
TRAIL_NAMES = ['Summit Run', 'Eagles Nest', 'Blue Bird', 'Family Way', 'Black Diamond', 'Powder Bowl',
               'North Face', 'Terrain Park', 'Learning Hill', 'Expert Chutes', 'Cruiser', 'Spring Trail']

# Feedback categories
FEEDBACK_CATEGORIES = ['Lifts', 'Food_Service', 'Staff', 'Facilities', 'Value', 'Snow_Conditions', 'Parking', 'Rentals', 'Lessons']
FEEDBACK_TYPES = ['NPS_Survey', 'Post_Visit_Survey', 'Online_Review', 'Complaint', 'Suggestion', 'Compliment']

# Marketing campaign enhancements
MARKETING_CHANNELS = ['Email', 'Paid_Search', 'Paid_Social', 'Display', 'Direct_Mail', 'SMS', 'Partner', 'Organic_Social']
CAMPAIGN_TYPES = ['Acquisition', 'Retention', 'Promotion', 'Brand', 'Reactivation', 'Cross_Sell', 'Loyalty']
ACQUISITION_CHANNELS = ['Organic_Search', 'Paid_Search', 'Social_Media', 'Referral', 'Direct', 'Partner', 'Email', 'Walk_In']

# Employee departments
EMPLOYEE_DEPARTMENTS = ['Lift Operations', 'Food & Beverage', 'Rental Services', 'Ticketing', 'Guest Services',
                        'Ski Patrol', 'Ski School', 'Grooming', 'Maintenance', 'Administration', 'Marketing']

# Grooming equipment
GROOMING_MACHINES = [f'GROMER{str(i).zfill(2)}' for i in range(1, 9)]

STAFFING_DEPARTMENTS = [
    {
        'id': 'LIFT',
        'department': 'Lift Operations',
        'job_role': 'Lift Operator',
        'base_staff': 14,
        'per_visitor': 1 / 180,
        'shift_hours': (7, 17),
        'location_pool': None
    },
    {
        'id': 'FNB',
        'department': 'Food & Beverage',
        'job_role': 'Service Associate',
        'base_staff': 18,
        'per_visitor': 1 / 70,
        'shift_hours': (8, 21),
        'location_pool': FB_LOCS
    },
    {
        'id': 'RENT',
        'department': 'Rental Services',
        'job_role': 'Rental Tech',
        'base_staff': 10,
        'per_visitor': 1 / 120,
        'shift_hours': (7, 19),
        'location_pool': RENTAL_LOCS
    },
    {
        'id': 'TIX',
        'department': 'Ticketing',
        'job_role': 'Ticket Agent',
        'base_staff': 8,
        'per_visitor': 1 / 220,
        'shift_hours': (7, 17),
        'location_pool': TICKET_LOCS
    },
    {
        'id': 'GUEST',
        'department': 'Guest Services',
        'job_role': 'Guest Ambassador',
        'base_staff': 6,
        'per_visitor': 1 / 260,
        'shift_hours': (8, 18),
        'location_pool': ['LOC021']
    }
]

MARKETING_TEMPLATES = [
    {
        'campaign_id_prefix': 'CAMP_PASS_RENEW',
        'campaign_name': 'Early Bird Season Pass Renewal',
        'channel': 'Email',
        'campaign_type': 'Retention',
        'audience_segment': 'Current Pass Holders',
        'personas': ['local_pass_holder', 'weekend_warrior', 'expert_skier'],
        'avg_value': 899,
        'open_rate': (0.32, 0.48),
        'click_rate': (0.08, 0.16),
        'conversion_rate': (0.02, 0.05)
    },
    {
        'campaign_id_prefix': 'CAMP_FAM_GETAWAY',
        'campaign_name': 'Family Winter Getaway',
        'channel': 'Email',
        'campaign_type': 'Acquisition',
        'audience_segment': 'Vacation Families',
        'personas': ['vacation_family'],
        'avg_value': 520,
        'open_rate': (0.28, 0.44),
        'click_rate': (0.07, 0.15),
        'conversion_rate': (0.03, 0.06)
    },
    {
        'campaign_id_prefix': 'CAMP_DAY_TRIP',
        'campaign_name': 'Weekend Warrior Flash Sale',
        'channel': 'SMS',
        'campaign_type': 'Promotion',
        'audience_segment': 'Weekend Warriors',
        'personas': ['weekend_warrior', 'day_tripper'],
        'avg_value': 175,
        'open_rate': (0.45, 0.62),
        'click_rate': (0.11, 0.20),
        'conversion_rate': (0.04, 0.08)
    },
    {
        'campaign_id_prefix': 'CAMP_RENTAL_DEMO',
        'campaign_name': 'High Performance Demo Days',
        'channel': 'Push Notification',
        'campaign_type': 'Cross-Sell',
        'audience_segment': 'Advanced Skiers',
        'personas': ['expert_skier', 'local_pass_holder'],
        'avg_value': 140,
        'open_rate': (0.30, 0.42),
        'click_rate': (0.10, 0.18),
        'conversion_rate': (0.05, 0.09)
    },
    {
        'campaign_id_prefix': 'CAMP_FIRST_TIMER',
        'campaign_name': 'Learn to Ski Bundle',
        'channel': 'Email',
        'campaign_type': 'Nurture',
        'audience_segment': 'First Timers',
        'personas': ['beginner', 'group_corporate'],
        'avg_value': 320,
        'open_rate': (0.26, 0.38),
        'click_rate': (0.06, 0.12),
        'conversion_rate': (0.03, 0.07)
    }
]

def build_daily_modifiers():
    """Pre-compute daily modifiers for vectorized probability calculations"""
    dates = pd.date_range(START_DATE, END_DATE, freq='D')

    modifiers = pd.DataFrame({
        'date': dates,
        'month': dates.month,
        'day_of_week': dates.dayofweek,  # 0=Monday, 5=Saturday, 6=Sunday
        'day': dates.day
    })

    # Season multiplier
    modifiers['season_mult'] = modifiers['month'].map({
        11: 0.5, 12: 1.2, 1: 1.5, 2: 1.4, 3: 1.1, 4: 0.7
    }).fillna(0)

    # Holiday boost
    modifiers['holiday_mult'] = 1.0
    modifiers.loc[(modifiers['month'] == 12) & (modifiers['day'] >= 20), 'holiday_mult'] = 2.5
    modifiers.loc[(modifiers['month'] == 1) & (modifiers['day'] <= 5), 'holiday_mult'] = 2.5
    modifiers.loc[(modifiers['month'] == 2) & (modifiers['day'].between(15, 21)), 'holiday_mult'] = 1.8
    modifiers.loc[(modifiers['month'] == 3) & (modifiers['day'].between(10, 24)), 'holiday_mult'] = 1.6

    # Day type
    modifiers['is_weekend'] = modifiers['day_of_week'] >= 5
    modifiers['is_saturday'] = modifiers['day_of_week'] == 5
    modifiers['is_ski_season'] = modifiers['month'].isin([11, 12, 1, 2, 3, 4])

    snowfall_values = []
    temp_high_values = []
    temp_low_values = []
    wind_speed_values = []
    storm_flags = []
    powder_flags = []
    base_depth_values = []
    base_depth = 38.0

    month_temp_high = {11: 35, 12: 28, 1: 25, 2: 27, 3: 32, 4: 38}

    for date in dates:
        month = date.month
        if month in [11, 12, 1, 2, 3, 4]:
            mean_snow = {11: 4.0, 12: 7.0, 1: 8.5, 2: 7.5, 3: 6.0, 4: 3.0}[month]
            snowfall = max(0.0, rng.normal(mean_snow, 3.0))
            temp_high = max(5.0, rng.normal(month_temp_high[month], 5.0))
        else:
            snowfall = 0.0
            temp_high = max(40.0, rng.normal(55.0, 8.0))
        temp_low = temp_high - rng.uniform(8.0, 18.0)
        wind_speed = float(np.clip(rng.normal(12.0, 5.0), 3.0, 45.0))
        storm = snowfall >= 12.0 or wind_speed >= 35.0
        powder = snowfall >= 6.0
        base_depth = max(18.0, min(140.0, base_depth * 0.97 + snowfall * 0.85))

        snowfall_values.append(round(snowfall, 2))
        temp_high_values.append(round(temp_high, 1))
        temp_low_values.append(round(temp_low, 1))
        wind_speed_values.append(round(wind_speed, 1))
        storm_flags.append(bool(storm))
        powder_flags.append(bool(powder))
        base_depth_values.append(round(base_depth, 2))

    modifiers['snowfall_inches'] = snowfall_values
    modifiers['base_depth_inches'] = base_depth_values
    modifiers['temp_high_f'] = temp_high_values
    modifiers['temp_low_f'] = temp_low_values
    modifiers['wind_speed_mph'] = wind_speed_values
    modifiers['storm_warning'] = storm_flags
    modifiers['is_powder_day'] = powder_flags
    modifiers['powder_boost'] = modifiers['is_powder_day'].apply(lambda x: 1.35 if x else 1.0)

    def classify_condition(snowfall, temp_high, storm):
        if snowfall >= 10:
            return 'Powder'
        if snowfall >= 5:
            return 'Fresh Snow'
        if storm:
            return 'Variable'
        if temp_high <= 28:
            return 'Packed Powder'
        if temp_high >= 38:
            return 'Spring Conditions'
        return 'Groomed'

    modifiers['snow_condition'] = [
        classify_condition(s, t, st)
        for s, t, st in zip(modifiers['snowfall_inches'], modifiers['temp_high_f'], modifiers['storm_warning'])
    ]

    return modifiers.set_index('date')

def generate_customers():
    """Generate 8,000 customers vectorized"""
    logger.info("Generating 8,000 customers...")

    all_customers = []
    cust_id = 1

    for persona, config in PERSONAS.items():
        count = config['count']

        # Vectorized age generation
        if persona == 'local_pass_holder':
            ages = rng.integers(25, 56, count)
        elif persona == 'weekend_warrior':
            ages = rng.integers(30, 51, count)
        elif persona == 'vacation_family':
            ages = rng.integers(8, 66, count)
        elif persona == 'expert_skier':
            ages = rng.integers(22, 46, count)
        else:
            ages = rng.integers(22, 61, count)

        birth_dates = [datetime.now() - timedelta(days=int(age*365.25)) for age in ages]

        # Pass holder assignments
        is_pass_holder = persona in ['local_pass_holder', 'weekend_warrior', 'expert_skier']

        # Generate customer records
        for i in range(count):
            pass_type = None
            if is_pass_holder:
                if persona == 'local_pass_holder':
                    pass_type = rng.choice(['TKT008', 'TKT009', 'TKT014'])
                elif persona == 'weekend_warrior':
                    pass_type = rng.choice(['TKT008', 'TKT009'])
                else:
                    pass_type = 'TKT008'

            # Geographic
            if persona == 'local_pass_holder':
                state, zip_code = 'CO', f'80{rng.integers(200, 300)}'
            elif persona in ['vacation_family', 'day_tripper']:
                state = rng.choice(['CA', 'TX', 'NY', 'FL', 'IL', 'WA', 'CO'])
                zip_code = fake.zipcode()
            else:
                state = rng.choice(['CO', 'WY', 'NM', 'UT'])
                zip_code = fake.zipcode()

            range_days = max(1, (END_DATE - START_DATE).days + 1)
            first_visit = START_DATE + timedelta(days=int(rng.integers(0, range_days)))
            acq_channel = rng.choice(ACQUISITION_CHANNELS, p=[0.20, 0.15, 0.15, 0.12, 0.18, 0.08, 0.07, 0.05])

            # Estimate lifetime value based on persona
            ltv_base = {'local_pass_holder': 3500, 'weekend_warrior': 1200, 'vacation_family': 800,
                       'day_tripper': 300, 'expert_skier': 2000, 'group_corporate': 500, 'beginner': 200}
            ltv = ltv_base.get(persona, 500) * rng.uniform(0.6, 1.5)

            all_customers.append({
                'customer_id': f'CUST{str(cust_id).zfill(6)}',
                'customer_name': fake.name(),
                'email': fake.email(),
                'phone': fake.phone_number(),
                'birth_date': birth_dates[i].strftime('%Y-%m-%d'),
                'customer_segment': persona,
                'is_pass_holder': is_pass_holder,
                'pass_type': pass_type,
                'first_visit_date': first_visit.strftime('%Y-%m-%d'),
                'home_zip_code': zip_code,
                'state': state,
                # New acquisition fields
                'acquisition_date': (first_visit - timedelta(days=int(rng.integers(0, 30)))).strftime('%Y-%m-%d'),
                'acquisition_channel': acq_channel,
                'acquisition_campaign_id': f"CAMP{str(rng.integers(1, 500)).zfill(5)}" if acq_channel not in ['Direct', 'Walk_In', 'Organic_Search'] else None,
                'acquisition_source': acq_channel,
                # Lifetime metrics
                'lifetime_value': round(ltv, 2),
                'total_visits': int(rng.integers(1, 50)) if is_pass_holder else int(rng.integers(1, 10)),
                'total_spend': round(ltv * rng.uniform(0.8, 1.2), 2),
                'avg_spend_per_visit': round(rng.uniform(50, 200), 2),
                'last_visit_date': (END_DATE - timedelta(days=int(rng.integers(0, 180)))).strftime('%Y-%m-%d'),
                'churn_risk_score': round(rng.uniform(0.05, 0.95), 2) if not is_pass_holder else round(rng.uniform(0.02, 0.3), 2),
                # Communication preferences
                'preferred_channel': rng.choice(['Email', 'SMS', 'Mail', 'App']),
                'email_opt_in': rng.random() < 0.85,
                'sms_opt_in': rng.random() < 0.35,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            cust_id += 1

    return pd.DataFrame(all_customers)

def get_daily_attendance_vectorized(current_date, persona_groups, daily_mod):
    """Vectorized daily attendance calculation"""
    visitors = []

    for persona, group in persona_groups.items():
        config = PERSONAS[persona]

        # Get base probability
        if persona == 'weekend_warrior':
            if daily_mod['is_saturday']:
                base_prob = config['base_prob']['saturday']
            elif daily_mod['is_weekend']:
                base_prob = config['base_prob']['sunday']
            else:
                base_prob = config['base_prob']['weekday']
        else:
            base_prob = config['base_prob']['weekend'] if daily_mod['is_weekend'] else config['base_prob']['weekday']

        # Calculate final probability
        final_prob = base_prob * daily_mod['season_mult'] * daily_mod['holiday_mult']
        final_prob *= daily_mod.get('powder_boost', 1.0)
        if daily_mod.get('storm_warning', False):
            final_prob *= 0.7
        final_prob = float(np.clip(final_prob, 0.0, 0.9))

        # Vectorized sampling
        visit_mask = rng.random(len(group)) < final_prob

        if visit_mask.any():
            visitors.append(group[visit_mask])

    return pd.concat(visitors, ignore_index=True) if visitors else pd.DataFrame()

def generate_weather_history(daily_modifiers):
    records = []
    for date, row in daily_modifiers.iterrows():
        for zone in WEATHER_ZONES:
            snowfall = max(0.0, row['snowfall_inches'] + rng.normal(0, 1.0))
            base_depth = max(18.0, row['base_depth_inches'] + rng.normal(0, 2.0))
            temp_high = row['temp_high_f'] + rng.normal(0, 1.5)
            temp_low = temp_high - rng.uniform(9, 16)
            wind_speed = float(np.clip(row['wind_speed_mph'] + rng.normal(0, 2.0), 3.0, 50.0))
            snow_condition = row['snow_condition']
            if snowfall >= 10:
                snow_condition = 'Powder'
            elif snowfall <= 1.5 and temp_high > 36:
                snow_condition = 'Spring Conditions'
            storm_warning = bool(row['storm_warning'] or wind_speed >= 38 or snowfall >= 14)
            records.append({
                'weather_date': date.strftime('%Y-%m-%d'),
                'mountain_zone': zone,
                'snow_condition': snow_condition,
                'snowfall_inches': round(snowfall, 2),
                'base_depth_inches': round(base_depth, 2),
                'temp_high_f': round(temp_high, 1),
                'temp_low_f': round(temp_low, 1),
                'wind_speed_mph': round(wind_speed, 1),
                'storm_warning': storm_warning,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
    return pd.DataFrame(records)


def generate_staffing_entries(current_date, visitors_count, daily_mod):
    entries = []
    if visitors_count is None:
        visitors_count = 0
    for dept in STAFFING_DEPARTMENTS:
        scheduled = dept['base_staff'] + visitors_count * dept['per_visitor']
        if daily_mod['is_weekend']:
            scheduled += 4
        if daily_mod.get('is_powder_day', False):
            scheduled += 3
        if daily_mod.get('storm_warning', False):
            scheduled -= 2
        scheduled = max(2, int(round(scheduled)))
        actual = max(1, int(round(scheduled * rng.uniform(0.9, 1.05))))
        coverage = round(actual / scheduled, 2)
        start_hour, end_hour = dept['shift_hours']
        shift_start = current_date.replace(hour=start_hour, minute=0)
        shift_end = current_date.replace(hour=end_hour, minute=0)
        location_id = None
        if dept['location_pool']:
            location_id = rng.choice(dept['location_pool'])
        schedule_id = f"STAFF{current_date.strftime('%Y%m%d')}{dept['id']}{str(rng.integers(0, 999)).zfill(3)}"
        entries.append({
            'schedule_id': schedule_id,
            'schedule_date': current_date.strftime('%Y-%m-%d'),
            'location_id': location_id,
            'department': dept['department'],
            'job_role': dept['job_role'],
            'scheduled_employees': scheduled,
            'actual_employees': actual,
            'coverage_ratio': coverage,
            'shift_start': shift_start.strftime('%Y-%m-%d %H:%M:%S'),
            'shift_end': shift_end.strftime('%Y-%m-%d %H:%M:%S'),
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    return entries


def generate_marketing_touches(customers_df):
    persona_counts = customers_df.groupby('customer_segment').size().to_dict()
    start_marketing = max(datetime(2021, 1, 1), START_DATE)
    send_dates = pd.date_range(start_marketing, END_DATE, freq='MS')
    touches = []
    counter = 1
    for send_date in send_dates:
        template = MARKETING_TEMPLATES[(counter - 1) % len(MARKETING_TEMPLATES)]
        target_count = sum(persona_counts.get(p, 0) for p in template['personas'])
        if target_count == 0:
            counter += 1
            continue
        open_rate = float(round(rng.uniform(*template['open_rate']), 4))
        click_candidate = float(round(rng.uniform(*template['click_rate']), 4))
        click_rate = float(round(min(open_rate, click_candidate), 4))
        conversion_rate = rng.uniform(*template['conversion_rate'])
        conversion_count = int(round(target_count * conversion_rate))
        revenue_attributed = round(conversion_count * template['avg_value'] * rng.uniform(0.9, 1.1), 2)
        touch_id = f"TOUCH{send_date.strftime('%Y%m')}{str(counter).zfill(4)}"
        campaign_id = f"{template['campaign_id_prefix']}_{send_date.strftime('%Y%m')}"
        touches.append({
            'touch_id': touch_id,
            'campaign_id': campaign_id,
            'campaign_name': template['campaign_name'],
            'campaign_channel': template['channel'],
            'campaign_type': template['campaign_type'],
            'audience_segment': template['audience_segment'],
            'send_date': send_date.strftime('%Y-%m-%d'),
            'target_count': target_count,
            'open_rate': open_rate,
            'click_rate': click_rate,
            'conversion_count': conversion_count,
            'revenue_attributed': revenue_attributed,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        counter += 1
    return pd.DataFrame(touches)


# ============================================================================
# NEW GENERATION FUNCTIONS - PHASE 1, 2, 3
# ============================================================================

def generate_instructors():
    """Generate ski school instructors"""
    logger.info("Generating instructors...")
    instructors = []
    for i in range(1, 46):  # 45 instructors
        level = rng.choice(INSTRUCTOR_LEVELS, p=[0.35, 0.35, 0.20, 0.10])
        specialties = list(rng.choice(INSTRUCTOR_SPECIALTIES, size=rng.integers(1, 4), replace=False))
        sport = rng.choice(['Ski', 'Snowboard', 'Both'], p=[0.6, 0.3, 0.1])

        instructors.append({
            'instructor_id': f'INST{str(i).zfill(3)}',
            'instructor_name': fake.name(),
            'certification_level': level,
            'specialties': ','.join(specialties),
            'languages': rng.choice(['English', 'English,Spanish', 'English,French', 'English,German'], p=[0.7, 0.15, 0.1, 0.05]),
            'sport_type': sport,
            'hire_date': (START_DATE - timedelta(days=int(rng.integers(30, 2000)))).strftime('%Y-%m-%d'),
            'hourly_rate': float(rng.choice([25, 30, 40, 55], p=[0.35, 0.35, 0.20, 0.10])),
            'avg_rating': round(rng.uniform(3.8, 5.0), 2),
            'total_lessons': int(rng.integers(50, 2000)),
            'active': True,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    return pd.DataFrame(instructors)


def generate_parking_lots():
    """Generate parking lot reference data"""
    logger.info("Generating parking lots...")
    df = pd.DataFrame(PARKING_LOTS)
    df['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return df


def generate_employees():
    """Generate employee roster"""
    logger.info("Generating employees...")
    employees = []
    emp_id = 1

    dept_counts = {
        'Lift Operations': 45, 'Food & Beverage': 60, 'Rental Services': 25,
        'Ticketing': 15, 'Guest Services': 12, 'Ski Patrol': 18,
        'Ski School': 45, 'Grooming': 12, 'Maintenance': 15, 'Administration': 10, 'Marketing': 8
    }

    job_titles = {
        'Lift Operations': ['Lift Operator', 'Senior Lift Operator', 'Lift Supervisor'],
        'Food & Beverage': ['Line Cook', 'Server', 'Cashier', 'F&B Supervisor'],
        'Rental Services': ['Rental Tech', 'Senior Rental Tech', 'Rental Manager'],
        'Ticketing': ['Ticket Agent', 'Senior Agent', 'Ticket Supervisor'],
        'Guest Services': ['Guest Ambassador', 'Concierge', 'Guest Services Manager'],
        'Ski Patrol': ['Patroller', 'Senior Patroller', 'Patrol Director'],
        'Ski School': ['Instructor', 'Senior Instructor', 'Ski School Director'],
        'Grooming': ['Groomer Operator', 'Senior Groomer', 'Grooming Supervisor'],
        'Maintenance': ['Technician', 'Senior Technician', 'Maintenance Manager'],
        'Administration': ['Admin Assistant', 'Coordinator', 'Manager'],
        'Marketing': ['Marketing Coordinator', 'Digital Specialist', 'Marketing Manager']
    }

    for dept, count in dept_counts.items():
        for i in range(count):
            is_supervisor = i < max(1, count // 10)
            emp_type = rng.choice(['Full_Time', 'Part_Time', 'Seasonal'], p=[0.3, 0.2, 0.5])
            titles = job_titles[dept]
            title = titles[-1] if is_supervisor else rng.choice(titles[:-1]) if len(titles) > 1 else titles[0]

            employees.append({
                'employee_id': f'EMP{str(emp_id).zfill(4)}',
                'employee_name': fake.name(),
                'department': dept,
                'job_title': title,
                'hire_date': (START_DATE - timedelta(days=int(rng.integers(30, 1500)))).strftime('%Y-%m-%d'),
                'termination_date': '',  # Empty = NULL in Snowflake
                'employment_type': emp_type,
                'hourly_rate': float(rng.integers(15, 45)),
                'certifications': None,
                'emergency_contact': fake.phone_number(),
                'home_zip': fake.zipcode(),
                'is_supervisor': is_supervisor,
                'reports_to': None,
                'active': True,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            emp_id += 1

    return pd.DataFrame(employees)


def generate_season_pass_sales(customers_df):
    """Generate season pass sales for pass holders"""
    logger.info("Generating season pass sales...")
    sales = []
    sale_id = 1

    pass_holders = customers_df[customers_df['is_pass_holder']]

    for season_start_year in range(START_DATE.year, END_DATE.year + 1):
        season = f"{season_start_year}-{season_start_year + 1}"

        for _, cust in pass_holders.iterrows():
            # Not all pass holders buy every season
            if rng.random() > 0.85:  # 85% buy each season
                continue

            # Purchase timing - early bird vs regular
            is_early_bird = rng.random() < 0.55
            if is_early_bird:
                purchase_month = rng.choice([6, 7, 8])
                discount = 0.22  # 22% early bird discount
            else:
                purchase_month = rng.choice([9, 10, 11, 12])
                discount = 0.0

            purchase_date = datetime(season_start_year, purchase_month, rng.integers(1, 28))

            pass_type = cust['pass_type'] if cust['pass_type'] else rng.choice(SEASON_PASSES)
            base_price = {'TKT008': 899, 'TKT009': 699, 'TKT010': 699, 'TKT011': 499,
                         'TKT012': 499, 'TKT013': 399, 'TKT014': 699, 'TKT018': 299}.get(pass_type, 899)

            discount_amount = round(base_price * discount, 2)
            purchase_amount = base_price - discount_amount

            # Renewal tracking
            is_renewal = sale_id > len(pass_holders) * 0.3  # After first season, most are renewals

            sales.append({
                'sale_id': f'PASS{str(sale_id).zfill(6)}',
                'customer_id': cust['customer_id'],
                'ticket_type_id': pass_type,
                'purchase_date': purchase_date.strftime('%Y-%m-%d'),
                'valid_season': season,
                'purchase_amount': float(purchase_amount),
                'original_price': float(base_price),
                'discount_amount': float(discount_amount),
                'payment_method': rng.choice(['Credit Card', 'Debit Card', 'Check'], p=[0.7, 0.2, 0.1]),
                'purchase_channel': rng.choice(['online', 'phone', 'in_person'], p=[0.65, 0.2, 0.15]),
                'is_renewal': is_renewal,
                'previous_pass_type': pass_type if is_renewal else None,
                'promo_code': 'EARLYBIRD' if is_early_bird else None,
                'campaign_id': f"CAMP_PASS_RENEW_{purchase_date.strftime('%Y%m')}" if is_renewal else f"CAMP_NEW_PASS_{purchase_date.strftime('%Y%m')}",
                'payment_plan': rng.random() < 0.15,
                'payment_plan_months': 4 if rng.random() < 0.15 else None,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            sale_id += 1

    return pd.DataFrame(sales)


def generate_marketing_campaigns():
    """Generate marketing campaigns with spend data"""
    logger.info("Generating marketing campaigns...")
    campaigns = []

    # Generate campaigns for each month in the date range
    campaign_dates = pd.date_range(START_DATE, END_DATE, freq='MS')
    camp_id = 1

    for start_date in campaign_dates:
        month = start_date.month

        # Determine number of campaigns based on season
        if month in [10, 11]:  # Pre-season
            n_campaigns = rng.integers(6, 10)
            budget_mult = 1.5
        elif month in [12, 1, 2]:  # Peak season
            n_campaigns = rng.integers(8, 14)
            budget_mult = 2.0
        elif month in [3, 4]:  # Spring
            n_campaigns = rng.integers(4, 7)
            budget_mult = 1.0
        else:  # Off-season
            n_campaigns = rng.integers(2, 5)
            budget_mult = 0.5

        for _ in range(n_campaigns):
            channel = rng.choice(MARKETING_CHANNELS, p=[0.30, 0.20, 0.18, 0.12, 0.05, 0.08, 0.04, 0.03])
            camp_type = rng.choice(CAMPAIGN_TYPES, p=[0.25, 0.25, 0.20, 0.10, 0.08, 0.07, 0.05])

            base_budget = {'Email': 500, 'Paid_Search': 5000, 'Paid_Social': 4000, 'Display': 3000,
                          'Direct_Mail': 8000, 'SMS': 300, 'Partner': 2000, 'Organic_Social': 200}.get(channel, 1000)
            budget = round(base_budget * budget_mult * rng.uniform(0.7, 1.4), 2)
            actual_spend = round(budget * rng.uniform(0.85, 1.05), 2)

            # Performance metrics
            if channel == 'Email':
                impressions = int(rng.integers(5000, 15000))
                ctr = rng.uniform(0.02, 0.05)
            elif channel in ['Paid_Search', 'Display']:
                impressions = int(rng.integers(50000, 200000))
                ctr = rng.uniform(0.01, 0.03)
            elif channel == 'Paid_Social':
                impressions = int(rng.integers(30000, 100000))
                ctr = rng.uniform(0.008, 0.025)
            else:
                impressions = int(rng.integers(1000, 10000))
                ctr = rng.uniform(0.01, 0.04)

            clicks = int(impressions * ctr)
            conv_rate = rng.uniform(0.01, 0.05)
            conversions = int(clicks * conv_rate)
            avg_order = rng.uniform(80, 250)
            revenue = round(conversions * avg_order, 2)
            cpa = round(actual_spend / max(conversions, 1), 2)
            roas = round(revenue / max(actual_spend, 1), 2)

            end_date = start_date + timedelta(days=int(rng.integers(7, 30)))

            campaigns.append({
                'campaign_id': f'CAMP{str(camp_id).zfill(5)}',
                'campaign_name': f"{camp_type} - {channel} - {start_date.strftime('%b %Y')}",
                'campaign_type': camp_type,
                'channel': channel,
                'target_audience': rng.choice(['All_Customers', 'Pass_Holders', 'Lapsed_Visitors', 'Prospects', 'Families', 'Locals']),
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'budget': float(budget),
                'actual_spend': float(actual_spend),
                'impressions': impressions,
                'clicks': clicks,
                'unique_visitors': int(clicks * 0.7),
                'conversions': conversions,
                'revenue_attributed': float(revenue),
                'cost_per_acquisition': float(cpa),
                'return_on_ad_spend': float(roas),
                'creative_variant': rng.choice(['A', 'B', 'Control']),
                'landing_page': f"/promo/{camp_type.lower()}-{start_date.strftime('%Y%m')}",
                'utm_source': channel.lower(),
                'utm_medium': 'cpc' if 'Paid' in channel else 'email' if channel == 'Email' else 'organic',
                'utm_campaign': f"{camp_type.lower()}_{start_date.strftime('%Y%m')}",
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            camp_id += 1

    return pd.DataFrame(campaigns)


def generate_customer_campaign_touches(customers_df, campaigns_df):
    """Generate individual customer-campaign interactions"""
    logger.info("Generating customer campaign touches...")
    touches = []
    touch_id = 1

    for _, camp in campaigns_df.iterrows():
        # Sample customers for this campaign
        target_size = min(len(customers_df), int(rng.integers(500, 3000)))
        target_customers = customers_df.sample(n=target_size, random_state=touch_id)

        for _, cust in target_customers.iterrows():
            delivered = rng.random() < 0.95
            opened = delivered and rng.random() < 0.35
            clicked = opened and rng.random() < 0.12
            converted = clicked and rng.random() < 0.03

            touch_date = datetime.strptime(camp['start_date'], '%Y-%m-%d') + timedelta(days=int(rng.integers(0, 7)))

            touches.append({
                'touch_id': f'TCH{str(touch_id).zfill(8)}',
                'customer_id': cust['customer_id'],
                'campaign_id': camp['campaign_id'],
                'touch_date': touch_date.strftime('%Y-%m-%d'),
                'touch_timestamp': f"{touch_date.strftime('%Y-%m-%d')} {rng.integers(6, 22):02d}:{rng.integers(0, 60):02d}:00",
                'channel': camp['channel'],
                'was_delivered': delivered,
                'was_opened': opened,
                'open_timestamp': f"{touch_date.strftime('%Y-%m-%d')} {rng.integers(6, 22):02d}:{rng.integers(0, 60):02d}:00" if opened else None,
                'was_clicked': clicked,
                'click_timestamp': f"{touch_date.strftime('%Y-%m-%d')} {rng.integers(6, 22):02d}:{rng.integers(0, 60):02d}:00" if clicked else None,
                'click_url': camp['landing_page'] if clicked else '',
                'converted': converted,
                'conversion_timestamp': f"{touch_date.strftime('%Y-%m-%d')} {rng.integers(6, 22):02d}:{rng.integers(0, 60):02d}:00" if converted else None,
                'conversion_type': rng.choice(['ticket_purchase', 'pass_purchase', 'rental']) if converted else '',
                'conversion_value': float(rng.integers(50, 300)) if converted else 0.0,
                'conversion_sale_id': '',
                'unsubscribed': not delivered and rng.random() < 0.02,
                'bounce_type': 'hard' if not delivered and rng.random() < 0.3 else ('soft' if not delivered else None),
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            touch_id += 1

            # Limit to avoid massive dataset
            if touch_id > 500000:
                logger.info("Limiting campaign touches to 500K records")
                return pd.DataFrame(touches)

    return pd.DataFrame(touches)


def generate_ski_lessons(customers_df, instructors_df, daily_modifiers):
    """Generate ski lesson bookings"""
    logger.info("Generating ski lessons...")
    lessons = []
    lesson_id = 1

    ski_dates = daily_modifiers[daily_modifiers['season_mult'] > 0].index
    instructor_ids = instructors_df['instructor_id'].tolist()

    for date in ski_dates:
        # Number of lessons varies by day type
        daily_mod = daily_modifiers.loc[date]
        if daily_mod['is_weekend']:
            n_lessons = rng.integers(25, 50)
        elif daily_mod['holiday_mult'] > 1.5:
            n_lessons = rng.integers(35, 60)
        else:
            n_lessons = rng.integers(10, 25)

        # Sample customers for lessons (beginners and families more likely)
        lesson_probs = customers_df['customer_segment'].map({
            'beginner': 0.4, 'vacation_family': 0.3, 'day_tripper': 0.15,
            'group_corporate': 0.25, 'weekend_warrior': 0.05,
            'local_pass_holder': 0.02, 'expert_skier': 0.01
        }).fillna(0.05)
        lesson_probs = lesson_probs / lesson_probs.sum()

        lesson_customers = customers_df.sample(n=min(n_lessons, len(customers_df)),
                                               weights=lesson_probs, replace=True, random_state=lesson_id)

        for _, cust in lesson_customers.iterrows():
            lesson_type = rng.choice(LESSON_TYPES, p=[0.25, 0.15, 0.35, 0.15, 0.05, 0.05])
            skill = rng.choice(SKILL_LEVELS, p=[0.25, 0.35, 0.25, 0.10, 0.05])
            duration = rng.choice([1.0, 2.0, 3.0, 4.0], p=[0.15, 0.45, 0.30, 0.10])

            base_price = {'Private': 200, 'Semi_Private': 150, 'Group': 80,
                         'Kids_Camp': 120, 'Race_Clinic': 180, 'Freestyle_Camp': 150}.get(lesson_type, 100)
            lesson_amount = base_price * duration

            lessons.append({
                'lesson_id': f'LES{str(lesson_id).zfill(7)}',
                'customer_id': cust['customer_id'],
                'lesson_date': date.strftime('%Y-%m-%d'),
                'lesson_start_time': f"{rng.choice([9, 10, 11, 13, 14]):02d}:00:00",
                'lesson_type': lesson_type,
                'sport_type': rng.choice(['Ski', 'Snowboard'], p=[0.75, 0.25]),
                'skill_level': skill,
                'duration_hours': float(duration),
                'instructor_id': rng.choice(instructor_ids),
                'group_size': 1 if lesson_type == 'Private' else (2 if lesson_type == 'Semi_Private' else rng.integers(4, 10)),
                'lesson_amount': float(lesson_amount),
                'rental_included': rng.random() < 0.6,
                'rental_amount': float(rng.integers(40, 70)) if rng.random() < 0.6 else None,
                'tip_amount': float(rng.integers(10, 50)) if rng.random() < 0.4 else None,
                'booking_channel': rng.choice(['online', 'phone', 'walk_up'], p=[0.5, 0.3, 0.2]),
                'booking_lead_days': int(rng.integers(0, 14)),
                'completed': rng.random() < 0.95,
                'cancellation_reason': None if rng.random() < 0.95 else rng.choice(['Weather', 'Customer_Request', 'Illness']),
                'student_rating': float(round(rng.uniform(3.5, 5.0), 1)) if rng.random() < 0.7 else None,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            lesson_id += 1

    return pd.DataFrame(lessons)


def generate_incidents(daily_modifiers):
    """Generate safety incidents"""
    logger.info("Generating incidents...")
    incidents = []
    inc_id = 1

    ski_dates = daily_modifiers[daily_modifiers['season_mult'] > 0].index

    for date in ski_dates:
        daily_mod = daily_modifiers.loc[date]

        # Base incident rate
        base_incidents = 2
        if daily_mod['is_weekend']:
            base_incidents += 1
        if daily_mod.get('is_powder_day', False):
            base_incidents += 1  # More people, more incidents
        if daily_mod.get('storm_warning', False):
            base_incidents -= 1  # Fewer people

        n_incidents = max(0, int(rng.poisson(base_incidents)))

        for _ in range(n_incidents):
            inc_type = rng.choice(INCIDENT_TYPES, p=[0.45, 0.10, 0.08, 0.15, 0.08, 0.10, 0.04])
            severity = rng.choice(INCIDENT_SEVERITIES, p=[0.60, 0.28, 0.10, 0.02])

            incidents.append({
                'incident_id': f'INC{str(inc_id).zfill(6)}',
                'incident_date': date.strftime('%Y-%m-%d'),
                'incident_time': f"{rng.integers(9, 16):02d}:{rng.integers(0, 60):02d}:00",
                'incident_timestamp': f"{date.strftime('%Y-%m-%d')} {rng.integers(9, 16):02d}:{rng.integers(0, 60):02d}:00",
                'incident_type': inc_type,
                'severity': severity,
                'location_id': rng.choice(LIFT_IDS[:6] + FB_LOCS[:3]) if inc_type != 'Lift_Stop' else None,
                'lift_id': rng.choice(LIFT_IDS) if inc_type in ['Lift_Stop', 'Equipment_Failure'] else None,
                'trail_name': rng.choice(TRAIL_NAMES) if inc_type in ['Injury', 'Collision', 'Lost_Skier'] else None,
                'customer_id': f'CUST{str(rng.integers(1, 8001)).zfill(6)}' if inc_type in ['Injury', 'Collision', 'Medical_Emergency'] else None,
                'customer_age': int(rng.integers(8, 75)) if inc_type in ['Injury', 'Collision'] else None,
                'customer_skill_level': rng.choice(SKILL_LEVELS) if inc_type in ['Injury', 'Collision'] else None,
                'description': f"{inc_type} incident on {date.strftime('%Y-%m-%d')}",
                'cause': rng.choice(['Speed', 'Terrain', 'Equipment', 'Weather', 'Other']),
                'weather_factor': daily_mod.get('storm_warning', False) or rng.random() < 0.2,
                'equipment_factor': inc_type == 'Equipment_Failure' or rng.random() < 0.15,
                'first_aid_rendered': inc_type in ['Injury', 'Collision', 'Medical_Emergency'],
                'transport_required': severity in ['Major', 'Critical'] or rng.random() < 0.1,
                'transport_type': rng.choice(['Toboggan', 'Snowmobile', 'Ambulance']) if severity in ['Major', 'Critical'] else None,
                'patrol_response_minutes': float(round(rng.uniform(2, 15), 1)),
                'resolution': 'Resolved on-site' if severity in ['Minor', 'Moderate'] else 'Transported to medical facility',
                'followup_required': severity in ['Major', 'Critical'],
                'report_filed': True,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            inc_id += 1

    return pd.DataFrame(incidents)


def generate_customer_feedback(customers_df, daily_modifiers):
    """Generate customer feedback and surveys"""
    logger.info("Generating customer feedback...")
    feedback = []
    fb_id = 1

    # Monthly NPS surveys
    survey_dates = pd.date_range(START_DATE, END_DATE, freq='MS')
    for survey_date in survey_dates:
        if survey_date.month not in [11, 12, 1, 2, 3, 4]:
            continue

        n_responses = rng.integers(150, 400)
        respondents = customers_df.sample(n=min(n_responses, len(customers_df)), random_state=fb_id)

        for _, cust in respondents.iterrows():
            nps = int(rng.choice(range(0, 11), p=[0.02, 0.01, 0.02, 0.03, 0.04, 0.08, 0.10, 0.15, 0.20, 0.20, 0.15]))
            sentiment = 'Positive' if nps >= 9 else ('Negative' if nps <= 6 else 'Neutral')

            feedback.append({
                'feedback_id': f'FB{str(fb_id).zfill(7)}',
                'customer_id': cust['customer_id'],
                'feedback_date': survey_date.strftime('%Y-%m-%d'),
                'feedback_type': 'NPS_Survey',
                'survey_id': f"NPS_{survey_date.strftime('%Y%m')}",
                'nps_score': nps,
                'satisfaction_score': min(5, max(1, int(nps / 2))),
                'likelihood_to_return': min(5, max(1, int(nps / 2) + rng.integers(-1, 2))),
                'likelihood_to_recommend': min(5, max(1, int(nps / 2))),
                'category': rng.choice(FEEDBACK_CATEGORIES),
                'subcategory': None,
                'sentiment': sentiment,
                'sentiment_score': float(round((nps - 5) / 5, 2)),
                'feedback_text': f"{'Great' if sentiment == 'Positive' else ('Poor' if sentiment == 'Negative' else 'Average')} experience" if rng.random() < 0.3 else '',
                'response_text': '',
                'response_date': '',  # Empty string = NULL in Snowflake
                'responded_by': '',
                'resolved': sentiment != 'Negative',
                'resolution_date': '',  # Empty string = NULL in Snowflake
                'escalated': sentiment == 'Negative' and nps <= 3,
                'source': 'Email_Survey',
                'visit_date': (survey_date - timedelta(days=int(rng.integers(1, 14)))).strftime('%Y-%m-%d'),
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            fb_id += 1

    return pd.DataFrame(feedback)


def generate_parking_occupancy(daily_modifiers):
    """Generate hourly parking occupancy data"""
    logger.info("Generating parking occupancy...")
    records = []
    rec_id = 1

    ski_dates = daily_modifiers[daily_modifiers['season_mult'] > 0].index
    lot_data = {lot['lot_id']: lot for lot in PARKING_LOTS}

    for date in ski_dates:
        daily_mod = daily_modifiers.loc[date]

        # Base occupancy multiplier
        base_mult = 0.4  # 40% base
        if daily_mod['is_weekend']:
            base_mult = 0.85
        if daily_mod['holiday_mult'] > 1.5:
            base_mult = 0.95
        if daily_mod.get('is_powder_day', False):
            base_mult = min(1.0, base_mult + 0.15)

        for lot_id, lot in lot_data.items():
            if lot['lot_type'] == 'Employee':
                continue  # Skip employee lot

            for hour in range(6, 18):  # 6 AM to 6 PM
                # Occupancy curve: builds in morning, peaks midday, declines afternoon
                if hour < 8:
                    hour_mult = 0.2
                elif hour < 10:
                    hour_mult = 0.6 + (hour - 8) * 0.2
                elif hour < 14:
                    hour_mult = 1.0
                elif hour < 16:
                    hour_mult = 0.8
                else:
                    hour_mult = 0.4

                occupancy_pct = min(1.0, base_mult * hour_mult * rng.uniform(0.85, 1.15))
                occupied = int(lot['total_spaces'] * occupancy_pct)

                # Overflow activation
                overflow_active = lot['lot_type'] == 'Overflow' and occupancy_pct > 0.5

                records.append({
                    'record_id': f'PKG{str(rec_id).zfill(8)}',
                    'record_date': date.strftime('%Y-%m-%d'),
                    'record_hour': hour,
                    'lot_id': lot_id,
                    'lot_name': lot['lot_name'],
                    'total_spaces': lot['total_spaces'],
                    'occupied_spaces': occupied,
                    'occupancy_percent': round(occupancy_pct * 100, 2),
                    'vehicles_entered': int(occupied * 0.1) if hour < 12 else 0,
                    'vehicles_exited': int(occupied * 0.15) if hour > 14 else 0,
                    'revenue_collected': float(occupied * lot['daily_max'] / 10) if lot['daily_max'] > 0 else 0,
                    'overflow_active': overflow_active,
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                rec_id += 1

    return pd.DataFrame(records)


def generate_lift_maintenance(daily_modifiers):
    """Generate lift maintenance records"""
    logger.info("Generating lift maintenance...")
    records = []
    maint_id = 1

    all_dates = pd.date_range(START_DATE, END_DATE, freq='D')

    for date in all_dates:
        # Scheduled maintenance more common in off-season
        month = date.month
        is_ski_season = month in [11, 12, 1, 2, 3, 4]

        if is_ski_season:
            # During season: fewer scheduled, more inspections
            if rng.random() < 0.05:  # 5% chance per day
                maint_type = rng.choice(['Scheduled', 'Inspection', 'Unscheduled'], p=[0.2, 0.6, 0.2])
            else:
                continue
        else:
            # Off-season: more maintenance
            if rng.random() < 0.15:
                maint_type = rng.choice(['Scheduled', 'Inspection', 'Emergency'], p=[0.6, 0.3, 0.1])
            else:
                continue

        lift_id = rng.choice(LIFT_IDS)
        downtime = int(rng.integers(30, 480)) if maint_type != 'Inspection' else int(rng.integers(15, 60))

        records.append({
            'maintenance_id': f'MAINT{str(maint_id).zfill(6)}',
            'lift_id': lift_id,
            'maintenance_date': date.strftime('%Y-%m-%d'),
            'maintenance_type': maint_type,
            'category': rng.choice(['Mechanical', 'Electrical', 'Safety', 'Haul_Rope', 'Sheave', 'Terminal']),
            'description': f"{maint_type} maintenance on {lift_id}",
            'start_time': f"{date.strftime('%Y-%m-%d')} {rng.integers(6, 10):02d}:00:00",
            'end_time': f"{date.strftime('%Y-%m-%d')} {rng.integers(10, 16):02d}:00:00",
            'downtime_minutes': downtime,
            'during_operating_hours': is_ski_season and rng.random() < 0.2,
            'parts_replaced': 'Various components' if maint_type == 'Scheduled' else None,
            'parts_cost': float(rng.integers(100, 5000)) if maint_type != 'Inspection' else 0,
            'labor_hours': float(round(downtime / 60, 1)),
            'labor_cost': float(round(downtime / 60 * 75, 2)),
            'total_cost': float(rng.integers(200, 8000)) if maint_type != 'Inspection' else float(rng.integers(50, 200)),
            'technician_id': f'EMP{str(rng.integers(200, 215)).zfill(4)}',
            'passed_inspection': maint_type == 'Inspection' or rng.random() < 0.95,
            'followup_required': rng.random() < 0.1,
            'notes': None,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        maint_id += 1

    return pd.DataFrame(records)


def generate_grooming_logs(daily_modifiers):
    """Generate grooming operation logs"""
    logger.info("Generating grooming logs...")
    records = []
    log_id = 1

    ski_dates = daily_modifiers[daily_modifiers['season_mult'] > 0].index

    for date in ski_dates:
        daily_mod = daily_modifiers.loc[date]

        # Grooming happens nightly
        n_trails_groomed = min(rng.integers(8, 14), len(TRAIL_NAMES))
        trails_to_groom = list(rng.choice(TRAIL_NAMES, size=n_trails_groomed, replace=False))

        for trail in trails_to_groom:
            duration = int(rng.integers(30, 90))

            records.append({
                'log_id': f'GROOM{str(log_id).zfill(7)}',
                'grooming_date': date.strftime('%Y-%m-%d'),
                'shift': 'Night',
                'trail_name': trail,
                'groomer_id': f'EMP{str(rng.integers(180, 192)).zfill(4)}',
                'machine_id': rng.choice(GROOMING_MACHINES),
                'start_time': f"{(date - timedelta(days=1)).strftime('%Y-%m-%d')} {rng.integers(18, 22):02d}:00:00",
                'end_time': f"{date.strftime('%Y-%m-%d')} {rng.integers(0, 5):02d}:00:00",
                'duration_minutes': duration,
                'grooming_type': rng.choice(['Full_Groom', 'Touch_Up', 'Park_Build'], p=[0.7, 0.25, 0.05]),
                'snow_depth_inches': float(round(daily_mod.get('base_depth_inches', 36) + rng.normal(0, 2), 1)),
                'conditions_before': rng.choice(['Choppy', 'Tracked_Out', 'Icy', 'Powder']),
                'conditions_after': 'Groomed',
                'fuel_used_gallons': float(round(duration * 0.4 + rng.normal(0, 2), 1)),
                'notes': None,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            log_id += 1

    return pd.DataFrame(records)


def generate_day_data(current_date, customers_today, daily_mod):
    """Generate all transaction types for a single day - FULLY VECTORIZED"""

    if len(customers_today) == 0:
        return None, None, None, None, None

    date_str = current_date.strftime('%Y%m%d')
    visit_date = current_date.strftime('%Y-%m-%d')
    n_visitors = len(customers_today)
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    is_powder_day = bool(daily_mod.get('is_powder_day', False))
    storm_warning = bool(daily_mod.get('storm_warning', False))
    is_weekend = daily_mod['is_weekend']
    snow_condition = daily_mod.get('snow_condition', 'Clear')
    wind_speed = daily_mod.get('wind_speed_mph', 10)

    weather = 'Stormy' if storm_warning else ('Windy' if wind_speed >= 25 else snow_condition if snow_condition in ['Powder', 'Fresh Snow'] else 'Clear')

    # Get arrays for vectorized operations
    personas = customers_today['customer_segment'].values
    customer_ids = customers_today['customer_id'].values
    is_pass_holder = customers_today['is_pass_holder'].values

    # === LIFT SCANS - VECTORIZED ===
    lap_mins = np.array([PERSONAS[p]['laps_range'][0] for p in personas])
    lap_maxs = np.array([PERSONAS[p]['laps_range'][1] for p in personas])
    num_laps = rng.integers(lap_mins, lap_maxs + 1)
    total_scans = int(num_laps.sum())

    scan_customer_ids = np.repeat(customer_ids, num_laps)
    scan_ids = [f'SCAN{date_str}{i:08d}' for i in range(total_scans)]

    # Generate lift assignments with popularity weighting
    lift_pop_array = np.array([LIFT_POPULARITY[lid] for lid in LIFT_IDS])
    lift_probs = lift_pop_array / lift_pop_array.sum()
    lift_ids = rng.choice(LIFT_IDS, size=total_scans, p=lift_probs)

    # Generate hours with peak distribution (more scans 9am-1pm)
    hour_probs = np.array([0.05, 0.12, 0.18, 0.20, 0.18, 0.12, 0.08, 0.07])  # 8am-4pm
    hours = rng.choice(range(8, 16), size=total_scans, p=hour_probs)
    minutes = rng.integers(0, 60, size=total_scans)
    scan_times = [f'{visit_date} {h:02d}:{m:02d}:00' for h, m in zip(hours, minutes)]
    temps = daily_mod.get('temp_low_f', 20) + rng.integers(0, 8, size=total_scans)

    # =========================================================================
    # REALISTIC WAIT TIME MODEL
    # Wait = Queue Length / (Effective Throughput per minute)
    # =========================================================================

    # 1. Calculate queue at each lift based on total visitors + time of day
    # Peak hours (10am-1pm) have 60% of visitors in line, off-peak 40%
    time_queue_factor = np.where((hours >= 10) & (hours <= 12), 0.60, 0.40)

    # 2. Get lift capacity and popularity for each scan's lift
    lift_capacities = np.array([LIFT_CAPACITY[lid] for lid in lift_ids])
    lift_popularities = np.array([LIFT_POPULARITY[lid] for lid in lift_ids])

    # 3. Calculate estimated queue at each lift
    # Queue = (Total visitors × Lift share × Time factor) / Number of lifts operating
    total_lift_share = lift_popularities / lift_pop_array.sum()
    estimated_queue = n_visitors * total_lift_share * time_queue_factor

    # 4. Calculate effective throughput (riders per minute)
    # Base: Lift capacity / 60 (convert hourly to per-minute)
    # Staffing efficiency: 0.7-0.95 depending on staffing levels
    staffing_efficiency = 0.85 if not is_weekend else 0.75  # Weekends have newer staff
    if storm_warning:
        staffing_efficiency *= 0.6  # Storm = slower loading

    effective_throughput = (lift_capacities / 60) * staffing_efficiency

    # 5. Calculate base wait time = Queue / Throughput
    base_wait = estimated_queue / np.clip(effective_throughput, 1, None)

    # 6. Add modifiers
    # Weekend: More crowded overall
    weekend_mult = rng.uniform(1.2, 1.5) if is_weekend else 1.0

    # Powder day: Everyone wants to ski, longer lines
    powder_mult = rng.uniform(1.1, 1.3) if is_powder_day else 1.0

    # Holiday: Significantly more crowded (get from daily_mod)
    holiday_mult = 1.0 + (daily_mod.get('holiday_mult', 1.0) - 1.0) * 0.3

    # 7. Combine and add realistic noise
    wait_times = base_wait * weekend_mult * powder_mult * holiday_mult
    wait_times = wait_times + rng.normal(0, 2.0, total_scans)  # ±2 min noise
    wait_times = np.clip(wait_times, 1, 45)  # 1-45 min realistic range
    wait_times = np.round(wait_times, 1)  # 1 decimal precision

    scans_df = pd.DataFrame({
        'scan_id': scan_ids, 'customer_id': scan_customer_ids, 'lift_id': lift_ids,
        'scan_timestamp': scan_times, 'wait_time_minutes': wait_times,
        'temperature_f': temps, 'weather_condition': weather, 'created_at': created_at
    })

    # === PASS USAGE - VECTORIZED ===
    hours_on_mtn = np.clip(rng.uniform(4, 8, n_visitors) + (1.0 if is_powder_day else 0), 2.5, 9.0).round(2)
    first_mins = rng.integers(0, 60, n_visitors)
    last_mins = rng.integers(0, 60, n_visitors)

    pass_df = pd.DataFrame({
        'usage_id': [f'USAGE{date_str}{cid}' for cid in customer_ids],
        'customer_id': customer_ids, 'visit_date': visit_date,
        'first_scan_time': [f'{visit_date} 08:{m:02d}:00' for m in first_mins],
        'last_scan_time': [f'{visit_date} 15:{m:02d}:00' for m in last_mins],
        'total_lift_rides': num_laps, 'hours_on_mountain': hours_on_mtn, 'created_at': created_at
    })

    # === TICKET SALES - VECTORIZED (non-pass holders only) ===
    non_pass_mask = ~is_pass_holder
    n_tickets = non_pass_mask.sum()
    if n_tickets > 0:
        ticket_cids = customer_ids[non_pass_mask]
        ticket_types = rng.choice(DAY_PASSES, size=n_tickets)
        channels = rng.choice(['online', 'window', 'kiosk'], size=n_tickets, p=[0.35, 0.60, 0.05])
        locations = np.where(channels == 'online', 'LOC019', rng.choice(['LOC017', 'LOC018', 'LOC020'], size=n_tickets))
        amounts = np.array([{'TKT001': 129, 'TKT002': 79, 'TKT003': 99, 'TKT004': 89}.get(t, 129) for t in ticket_types])
        purchase_hours = rng.integers(7, 11, n_tickets)
        purchase_mins = rng.integers(0, 60, n_tickets)

        sales_df = pd.DataFrame({
            'sale_id': [f'SALE{date_str}{i:06d}' for i in range(n_tickets)],
            'customer_id': ticket_cids, 'ticket_type_id': ticket_types, 'location_id': locations,
            'purchase_timestamp': [f'{visit_date} {h:02d}:{m:02d}:00' for h, m in zip(purchase_hours, purchase_mins)],
            'valid_from_date': visit_date, 'valid_to_date': visit_date, 'purchase_amount': amounts,
            'payment_method': rng.choice(['Credit Card', 'Debit Card', 'Cash'], size=n_tickets),
            'purchase_channel': channels, 'created_at': created_at
        })
    else:
        sales_df = pd.DataFrame()

    # === RENTALS - VECTORIZED ===
    rental_probs = np.array([PERSONAS[p]['rental_prob'] for p in personas])
    rental_mask = rng.random(n_visitors) < rental_probs
    n_rentals = rental_mask.sum()
    if n_rentals > 0:
        rental_cids = customer_ids[rental_mask]
        rental_products = rng.choice(RENTAL_PRODS, size=n_rentals)
        rental_locs = rng.choice(RENTAL_LOCS, size=n_rentals)
        rental_amounts = rng.integers(40, 70, n_rentals)
        rental_hours = rng.integers(7, 11, n_rentals)

        rent_df = pd.DataFrame({
            'rental_id': [f'RENT{date_str}{i:06d}' for i in range(n_rentals)],
            'customer_id': rental_cids, 'location_id': rental_locs, 'product_id': rental_products,
            'rental_timestamp': [f'{visit_date} {h:02d}:00:00' for h in rental_hours],
            'return_timestamp': [f'{visit_date} 16:00:00'] * n_rentals,
            'rental_duration_hours': 8.0, 'rental_amount': rental_amounts, 'created_at': created_at
        })
    else:
        rent_df = pd.DataFrame()

    # === FOOD & BEVERAGE - VECTORIZED ===
    fb_counts = np.array([rng.integers(*PERSONAS[p]['fb_trans']) for p in personas])
    total_fb = int(fb_counts.sum())
    fb_cids = np.repeat(customer_ids, fb_counts)
    fb_hours = rng.choice([8,9,10,11,12,13,14,15,16], size=total_fb, p=[0.05,0.08,0.10,0.12,0.25,0.20,0.10,0.08,0.02])
    fb_mins = rng.integers(0, 60, total_fb)
    fb_locs = rng.choice(FB_LOCS, size=total_fb)
    fb_prods = rng.choice(FOOD_PRODS + BEV_PRODS, size=total_fb)
    fb_qtys = rng.integers(1, 3, total_fb)
    fb_prices = rng.integers(5, 15, total_fb)

    fb_df = pd.DataFrame({
        'transaction_id': [f'FB{date_str}{i:08d}' for i in range(total_fb)],
        'customer_id': fb_cids, 'location_id': fb_locs, 'product_id': fb_prods,
        'transaction_timestamp': [f'{visit_date} {h:02d}:{m:02d}:00' for h, m in zip(fb_hours, fb_mins)],
        'quantity': fb_qtys, 'unit_price': fb_prices, 'total_amount': fb_qtys * fb_prices,
        'payment_method': rng.choice(['Credit Card', 'Debit Card', 'Cash', 'Mobile Pay'], size=total_fb),
        'created_at': created_at
    })

    return scans_df, pass_df, sales_df, rent_df, fb_df

def main():
    args = parse_args()
    overall_start = time.perf_counter()
    global START_DATE, END_DATE
    if args.start_date:
        START_DATE = args.start_date
    if args.end_date:
        END_DATE = args.end_date
    if END_DATE < START_DATE:
        raise ValueError("End date must be on or after start date.")
    logger.info("=" * 80)
    logger.info("OPTIMIZED SKI RESORT DATA GENERATION")
    logger.info("=" * 80)
    logger.info("Date range: %s -> %s", START_DATE.strftime('%Y-%m-%d'), END_DATE.strftime('%Y-%m-%d'))
    logger.info("Export mode: %s", "CSV-only" if args.export_only else "Load to Snowflake")
    logger.info("Progress interval: every %d days", max(1, args.progress_interval))

    customers_start = time.perf_counter()
    customers_df = generate_customers()
    logger.info("✓ Generated %s customers in %.2fs", f"{len(customers_df):,}", time.perf_counter() - customers_start)

    logger.info("Pre-computing daily modifiers...")
    modifiers_start = time.perf_counter()
    daily_modifiers = build_daily_modifiers()
    weather_df = generate_weather_history(daily_modifiers)
    logger.info("✓ Generated %s weather rows in %.2fs", f"{len(weather_df):,}", time.perf_counter() - modifiers_start)

    persona_groups = {
        persona: customers_df[customers_df['customer_segment'] == persona]
        for persona in PERSONAS.keys()
    }
    logger.info("✓ Grouped %s customers by persona", f"{len(customers_df):,}")

    logger.info("Generating transactional data...")
    all_scans_dfs = []
    all_usage_dfs = []
    all_sales_dfs = []
    all_rentals_dfs = []
    all_fb_dfs = []
    all_staffing_rows = []
    total_visitors = 0
    ski_season_dates = daily_modifiers[daily_modifiers['is_ski_season']].index
    progress_interval = max(1, args.progress_interval)

    for idx, current_date in enumerate(tqdm(ski_season_dates, desc="Processing days")):
        daily_mod = daily_modifiers.loc[current_date]
        customers_today = get_daily_attendance_vectorized(current_date.to_pydatetime(), persona_groups, daily_mod)
        visitor_count = len(customers_today)
        total_visitors += visitor_count
        all_staffing_rows.extend(
            generate_staffing_entries(current_date.to_pydatetime(), visitor_count, daily_mod)
        )
        if idx % progress_interval == 0:
            logger.info(
                "Day %d/%d %s — visitors: %s, powder: %s, storm: %s",
                idx + 1,
                len(ski_season_dates),
                current_date.strftime('%Y-%m-%d'),
                f"{visitor_count:,}",
                daily_mod.get('is_powder_day', False),
                daily_mod.get('storm_warning', False)
            )
        if visitor_count > 0:
            scans_df, usage_df, sales_df, rentals_df, fb_df = generate_day_data(
                current_date.to_pydatetime(), customers_today, daily_mod
            )
            if scans_df is not None and len(scans_df) > 0:
                all_scans_dfs.append(scans_df)
            if usage_df is not None and len(usage_df) > 0:
                all_usage_dfs.append(usage_df)
            if sales_df is not None and len(sales_df) > 0:
                all_sales_dfs.append(sales_df)
            if rentals_df is not None and len(rentals_df) > 0:
                all_rentals_dfs.append(rentals_df)
            if fb_df is not None and len(fb_df) > 0:
                all_fb_dfs.append(fb_df)

    logger.info("\n✓ Concatenating DataFrames...")
    concat_start = time.perf_counter()
    lift_scans_df = pd.concat(all_scans_dfs, ignore_index=True) if all_scans_dfs else pd.DataFrame()
    pass_usage_df = pd.concat(all_usage_dfs, ignore_index=True) if all_usage_dfs else pd.DataFrame()
    ticket_sales_df = pd.concat(all_sales_dfs, ignore_index=True) if all_sales_dfs else pd.DataFrame()
    rentals_df = pd.concat(all_rentals_dfs, ignore_index=True) if all_rentals_dfs else pd.DataFrame()
    fb_df = pd.concat(all_fb_dfs, ignore_index=True) if all_fb_dfs else pd.DataFrame()
    staffing_df = pd.DataFrame(all_staffing_rows) if all_staffing_rows else pd.DataFrame()
    marketing_df = generate_marketing_touches(customers_df)
    logger.info("✓ Concatenated tables in %.2fs", time.perf_counter() - concat_start)

    # =========================================================================
    # PHASE 1-3: GENERATE ALL NEW TABLES
    # =========================================================================
    logger.info("\nGenerating Phase 1-3 data (new tables)...")
    phase_start = time.perf_counter()

    # Reference tables
    instructors_df = generate_instructors()
    parking_lots_df = generate_parking_lots()
    employees_df = generate_employees()

    # Season pass sales
    season_pass_sales_df = generate_season_pass_sales(customers_df)

    # Marketing campaigns and touches
    marketing_campaigns_df = generate_marketing_campaigns()
    customer_campaign_touches_df = generate_customer_campaign_touches(customers_df, marketing_campaigns_df)

    # Lessons, incidents, feedback
    ski_lessons_df = generate_ski_lessons(customers_df, instructors_df, daily_modifiers)
    incidents_df = generate_incidents(daily_modifiers)
    customer_feedback_df = generate_customer_feedback(customers_df, daily_modifiers)

    # Parking and maintenance
    parking_occupancy_df = generate_parking_occupancy(daily_modifiers)
    lift_maintenance_df = generate_lift_maintenance(daily_modifiers)
    grooming_logs_df = generate_grooming_logs(daily_modifiers)

    logger.info("✓ Generated Phase 1-3 data in %.2fs", time.perf_counter() - phase_start)

    logger.info(f"\n{'='*80}")
    logger.info("DATA GENERATION SUMMARY")
    logger.info(f"{'='*80}")
    logger.info("== CORE TABLES ==")
    logger.info(f"Customers:             {len(customers_df):>10,}")
    logger.info(f"Unique visitors:       {total_visitors:>10,}")
    logger.info(f"Lift scans:            {len(lift_scans_df):>10,}")
    logger.info(f"Pass usage:            {len(pass_usage_df):>10,}")
    logger.info(f"Ticket sales:          {len(ticket_sales_df):>10,}")
    logger.info(f"Rentals:               {len(rentals_df):>10,}")
    logger.info(f"F&B transactions:      {len(fb_df):>10,}")
    logger.info(f"Weather records:       {len(weather_df):>10,}")
    logger.info(f"Staffing shifts:       {len(staffing_df):>10,}")
    logger.info(f"Marketing touches:     {len(marketing_df):>10,}")
    logger.info("== PHASE 1: MARKETING & PASSES ==")
    logger.info(f"Season pass sales:     {len(season_pass_sales_df):>10,}")
    logger.info(f"Marketing campaigns:   {len(marketing_campaigns_df):>10,}")
    logger.info(f"Campaign touches:      {len(customer_campaign_touches_df):>10,}")
    logger.info("== PHASE 2: LESSONS & SAFETY ==")
    logger.info(f"Ski lessons:           {len(ski_lessons_df):>10,}")
    logger.info(f"Incidents:             {len(incidents_df):>10,}")
    logger.info(f"Customer feedback:     {len(customer_feedback_df):>10,}")
    logger.info("== PHASE 3: OPERATIONS ==")
    logger.info(f"Instructors:           {len(instructors_df):>10,}")
    logger.info(f"Employees:             {len(employees_df):>10,}")
    logger.info(f"Parking lots:          {len(parking_lots_df):>10,}")
    logger.info(f"Parking occupancy:     {len(parking_occupancy_df):>10,}")
    logger.info(f"Lift maintenance:      {len(lift_maintenance_df):>10,}")
    logger.info(f"Grooming logs:         {len(grooming_logs_df):>10,}")
    logger.info(f"{'='*80}\n")

    # Define datasets for export/save
    datasets = {
        # Core tables
        'customers': customers_df,
        'lift_scans': lift_scans_df,
        'pass_usage': pass_usage_df,
        'ticket_sales': ticket_sales_df,
        'rentals': rentals_df,
        'food_beverage': fb_df,
        'weather_conditions': weather_df,
        'staffing_schedule': staffing_df,
        'marketing_touches': marketing_df,
        # Phase 1
        'season_pass_sales': season_pass_sales_df,
        'marketing_campaigns': marketing_campaigns_df,
        'customer_campaign_touches': customer_campaign_touches_df,
        # Phase 2
        'ski_lessons': ski_lessons_df,
        'incidents': incidents_df,
        'customer_feedback': customer_feedback_df,
        # Phase 3 - Reference
        'instructors': instructors_df,
        'employees': employees_df,
        'parking_lots': parking_lots_df,
        # Phase 3 - Operational
        'parking_occupancy': parking_occupancy_df,
        'lift_maintenance': lift_maintenance_df,
        'grooming_logs': grooming_logs_df,
    }

    # Save locally if requested (either --export-only or --save-local)
    if args.export_only or args.save_local:
        export_dir = Path(args.export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Saving data locally to {export_dir}...")
        for name, df in datasets.items():
            if df is None or df.empty:
                logger.info("Skipping %s export (no rows)", name)
                continue
            out_path = export_dir / f"{name}.csv.gz"
            df.to_csv(out_path, index=False, compression='gzip')
            logger.info("Saved %s rows to %s", f"{len(df):,}", out_path)
        logger.info("✓ Local save complete!")

        if args.export_only:
            logger.info("Export-only mode. Snowflake load skipped.")
            logger.info("Total runtime: %.2f minutes", (time.perf_counter() - overall_start) / 60)
            return

    logger.info("Loading to Snowflake...")
    load_start = time.perf_counter()
    # Prefer env-var driven connection (portable across envs); fall back to
    # snow CLI 'snowflake_agents' connection for local use.
    try:
        conn = SnowflakeConnection.from_env()
    except Exception as e:
        logger.info(f"from_env failed ({e}); trying snow CLI 'snowflake_agents'")
        conn = SnowflakeConnection.from_snow_cli('snowflake_agents')
    conn.execute(f"USE DATABASE {DATABASE}")
    conn.execute(f"USE SCHEMA {RAW_SCHEMA}")

    def load_table(df, table_name, batch_size=100000):
        """Helper to load DataFrame using PUT/COPY INTO for robust NULL handling.

        Uses write_pandas(auto_create_table=True, overwrite=True) on first load
        so that a fresh environment (no pre-existing tables) bootstraps itself.
        """
        import tempfile
        import os

        if df is None or df.empty:
            logger.info("Skipping %s (empty)", table_name)
            return
        df = df.copy()
        df.columns = df.columns.str.upper()
        n_rows = len(df)
        logger.info(f"Loading {n_rows:,} {table_name}...")

        # Check if table exists; if not, use write_pandas to auto-create
        try:
            conn.session.sql(f"DESC TABLE {table_name}").collect()
            table_exists = True
        except Exception:
            table_exists = False

        if not table_exists:
            logger.info(f"  table {table_name} does not exist — creating via write_pandas")
            # write_pandas uploads via internal stage + COPY; auto_create_table
            # infers column types from the DataFrame.
            conn.session.write_pandas(
                df,
                table_name=table_name,
                auto_create_table=True,
                overwrite=True,
                quote_identifiers=False,
            )
            logger.info(f"  ✓ Created + loaded {table_name}")
            return

        # Write to temp CSV file (empty string = NULL)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            df.to_csv(f, index=False, header=True, na_rep='')
            temp_file = f.name

        try:
            # Truncate table first
            conn.execute(f"TRUNCATE TABLE IF EXISTS {table_name}")

            # PUT file to table stage
            put_sql = f"PUT 'file://{temp_file}' @%{table_name} AUTO_COMPRESS=TRUE OVERWRITE=TRUE"
            conn.execute(put_sql)

            # COPY INTO with NULL handling and explicit column list
            cols = ', '.join(df.columns)
            copy_sql = f"""
                COPY INTO {table_name} ({cols})
                FROM @%{table_name}
                FILE_FORMAT = (
                    TYPE = 'CSV'
                    SKIP_HEADER = 1
                    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
                    NULL_IF = ('')
                    EMPTY_FIELD_AS_NULL = TRUE
                )
                ON_ERROR = 'ABORT_STATEMENT'
            """
            result = conn.execute(copy_sql)
            logger.info(f"  ✓ Copied {table_name}")

            # Clean up stage
            conn.execute(f"REMOVE @%{table_name}")
        finally:
            os.unlink(temp_file)

    # Core tables
    load_table(customers_df, "CUSTOMERS")
    load_table(lift_scans_df, "LIFT_SCANS")
    load_table(pass_usage_df, "PASS_USAGE")
    load_table(ticket_sales_df, "TICKET_SALES")
    load_table(rentals_df, "RENTALS")
    load_table(fb_df, "FOOD_BEVERAGE")
    load_table(weather_df, "WEATHER_CONDITIONS")
    load_table(staffing_df, "STAFFING_SCHEDULE")
    load_table(marketing_df, "MARKETING_TOUCHES")

    # Phase 1 - Marketing & Passes
    load_table(season_pass_sales_df, "SEASON_PASS_SALES")
    load_table(marketing_campaigns_df, "MARKETING_CAMPAIGNS")
    load_table(customer_campaign_touches_df, "CUSTOMER_CAMPAIGN_TOUCHES")

    # Phase 2 - Lessons & Safety
    load_table(ski_lessons_df, "SKI_LESSONS")
    load_table(incidents_df, "INCIDENTS")
    load_table(customer_feedback_df, "CUSTOMER_FEEDBACK")

    # Phase 3 - Reference tables
    load_table(instructors_df, "INSTRUCTORS")
    load_table(employees_df, "EMPLOYEES")
    load_table(parking_lots_df, "PARKING_LOTS")

    # Phase 3 - Operational
    load_table(parking_occupancy_df, "PARKING_OCCUPANCY")
    load_table(lift_maintenance_df, "LIFT_MAINTENANCE")
    load_table(grooming_logs_df, "GROOMING_LOGS")

    results = conn.fetch("""
        SELECT 'CUSTOMERS' as t, COUNT(*) as c FROM CUSTOMERS
        UNION ALL SELECT 'LIFT_SCANS', COUNT(*) FROM LIFT_SCANS
        UNION ALL SELECT 'PASS_USAGE', COUNT(*) FROM PASS_USAGE
        UNION ALL SELECT 'TICKET_SALES', COUNT(*) FROM TICKET_SALES
        UNION ALL SELECT 'RENTALS', COUNT(*) FROM RENTALS
        UNION ALL SELECT 'FOOD_BEVERAGE', COUNT(*) FROM FOOD_BEVERAGE
        UNION ALL SELECT 'WEATHER_CONDITIONS', COUNT(*) FROM WEATHER_CONDITIONS
        UNION ALL SELECT 'STAFFING_SCHEDULE', COUNT(*) FROM STAFFING_SCHEDULE
        UNION ALL SELECT 'MARKETING_TOUCHES', COUNT(*) FROM MARKETING_TOUCHES
        UNION ALL SELECT 'SEASON_PASS_SALES', COUNT(*) FROM SEASON_PASS_SALES
        UNION ALL SELECT 'MARKETING_CAMPAIGNS', COUNT(*) FROM MARKETING_CAMPAIGNS
        UNION ALL SELECT 'CUSTOMER_CAMPAIGN_TOUCHES', COUNT(*) FROM CUSTOMER_CAMPAIGN_TOUCHES
        UNION ALL SELECT 'SKI_LESSONS', COUNT(*) FROM SKI_LESSONS
        UNION ALL SELECT 'INCIDENTS', COUNT(*) FROM INCIDENTS
        UNION ALL SELECT 'CUSTOMER_FEEDBACK', COUNT(*) FROM CUSTOMER_FEEDBACK
        UNION ALL SELECT 'INSTRUCTORS', COUNT(*) FROM INSTRUCTORS
        UNION ALL SELECT 'EMPLOYEES', COUNT(*) FROM EMPLOYEES
        UNION ALL SELECT 'PARKING_LOTS', COUNT(*) FROM PARKING_LOTS
        UNION ALL SELECT 'PARKING_OCCUPANCY', COUNT(*) FROM PARKING_OCCUPANCY
        UNION ALL SELECT 'LIFT_MAINTENANCE', COUNT(*) FROM LIFT_MAINTENANCE
        UNION ALL SELECT 'GROOMING_LOGS', COUNT(*) FROM GROOMING_LOGS
    """)

    logger.info(f"\n{'='*80}")
    logger.info("SNOWFLAKE DATA VERIFICATION")
    logger.info(f"{'='*80}")
    for r in results:
        logger.info(f"{r[0]:<20} {r[1]:>10,} rows")
    logger.info(f"{'='*80}\n")
    conn.close()
    logger.info("✓✓✓ COMPLETE! Ready for dbt run")
    logger.info("Snowflake load time: %.2f minutes", (time.perf_counter() - load_start) / 60)
    logger.info("Total runtime: %.2f minutes", (time.perf_counter() - overall_start) / 60)

if __name__ == "__main__":
    main()
