"""
Shared constants and utilities for ski resort data generation.
Single source of truth for all data generation scripts.
"""

import numpy as np
from datetime import datetime

# =============================================================================
# RANDOM NUMBER GENERATOR (seeded for reproducibility in full generation)
# =============================================================================
def get_rng(seed=None):
    """Get a random number generator. Use seed=42 for reproducible full generation."""
    return np.random.default_rng(seed)

# Default unseeded for incremental (truly random)
rng = get_rng()

# =============================================================================
# DATE CONFIGURATION
# =============================================================================
DEFAULT_START_DATE = datetime(2020, 11, 1)  # 5 ski seasons
DEFAULT_END_DATE = datetime.now()

# =============================================================================
# CUSTOMER PERSONAS - Behavioral patterns for realistic data
# =============================================================================
PERSONAS = {
    'local_pass_holder': {
        'base_prob': {'weekday': 0.12, 'weekend': 0.08},
        'laps_range': (15, 25),
        'rental_prob': 0.05,
        'fb_trans': (1, 3),
        'description': 'Frequent local visitors with season passes'
    },
    'weekend_warrior': {
        'base_prob': {'weekday': 0.02, 'saturday': 0.15, 'sunday': 0.08},
        'laps_range': (10, 15),
        'rental_prob': 0.15,
        'fb_trans': (2, 4),
        'description': 'Regular weekend visitors'
    },
    'vacation_family': {
        'base_prob': {'weekday': 0.025, 'weekend': 0.035},
        'laps_range': (6, 10),
        'rental_prob': 0.85,
        'fb_trans': (3, 6),
        'description': 'Families on ski vacations'
    },
    'day_tripper': {
        'base_prob': {'weekday': 0.005, 'weekend': 0.015},
        'laps_range': (8, 12),
        'rental_prob': 0.45,
        'fb_trans': (1, 2),
        'description': 'Occasional day visitors'
    },
    'expert_skier': {
        'base_prob': {'weekday': 0.12, 'weekend': 0.12},
        'laps_range': (18, 28),
        'rental_prob': 0.20,
        'fb_trans': (0, 2),
        'description': 'Experienced skiers seeking challenging terrain'
    },
    'group_corporate': {
        'base_prob': {'weekday': 0.008, 'weekend': 0.002},
        'laps_range': (5, 10),
        'rental_prob': 0.70,
        'fb_trans': (3, 5),
        'description': 'Corporate groups and events'
    },
    'beginner': {
        'base_prob': {'weekday': 0.01, 'weekend': 0.01},
        'laps_range': (4, 7),
        'rental_prob': 0.95,
        'fb_trans': (2, 4),
        'description': 'New skiers learning the sport'
    }
}

# Customer distribution (must sum to 1.0)
PERSONA_DISTRIBUTION = {
    'local_pass_holder': 0.15,
    'weekend_warrior': 0.25,
    'vacation_family': 0.30,
    'day_tripper': 0.20,
    'expert_skier': 0.05,
    'group_corporate': 0.03,
    'beginner': 0.02
}

# =============================================================================
# LIFT CONFIGURATION
# =============================================================================
LIFT_IDS = [f'L{str(i+1).zfill(3)}' for i in range(18)]

# Lift capacity per hour (riders/hour)
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

# Lift popularity weights (higher = more traffic)
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

# =============================================================================
# LOCATION IDs
# =============================================================================
RENTAL_LOCS = ['LOC001', 'LOC002', 'LOC003', 'LOC004', 'LOC005', 'LOC006']
FB_LOCS = ['LOC007', 'LOC008', 'LOC009', 'LOC010', 'LOC011', 'LOC012',
           'LOC013', 'LOC014', 'LOC015', 'LOC016']
TICKET_LOCS = ['LOC017', 'LOC018', 'LOC019', 'LOC020']

# =============================================================================
# PRODUCT IDs
# =============================================================================
RENTAL_PRODS = [f'PROD{str(i).zfill(3)}' for i in range(1, 14)]
FB_PRODS = [f'PROD{str(i).zfill(3)}' for i in range(14, 32)]

# =============================================================================
# TICKET TYPES
# =============================================================================
DAY_PASSES = ['TKT001', 'TKT002', 'TKT003', 'TKT004', 'TKT015', 'TKT016']
TICKET_PRICES = {
    'TKT001': 129,  # Adult Day Pass
    'TKT002': 79,   # Child Day Pass
    'TKT003': 99,   # Senior Day Pass
    'TKT004': 89,   # Half Day Pass
    'TKT015': 129,
    'TKT016': 129,
}

# =============================================================================
# WEATHER & ZONES
# =============================================================================
WEATHER_ZONES = ['Summit Peak', 'North Ridge', 'Alpine Bowl', 'Village Base']

SNOW_CONDITIONS = ['Fresh Snow', 'Groomed', 'Packed Powder', 'Spring Conditions', 'Variable']

# Monthly weather averages
MONTHLY_SNOWFALL_MEAN = {11: 4.0, 12: 7.0, 1: 8.5, 2: 7.5, 3: 6.0, 4: 3.0}
MONTHLY_BASE_TEMP = {11: 30, 12: 25, 1: 20, 2: 22, 3: 28, 4: 35}

# =============================================================================
# STAFFING CONFIGURATION
# =============================================================================
STAFFING_DEPARTMENTS = [
    {'id': 'LIFT', 'department': 'Lift Operations', 'job_role': 'Lift Operator',
     'base_staff': 18, 'weekend_mult': 1.3, 'location_pool': None},
    {'id': 'RENT', 'department': 'Rentals', 'job_role': 'Rental Tech',
     'base_staff': 8, 'weekend_mult': 1.5, 'location_pool': RENTAL_LOCS},
    {'id': 'FOOD', 'department': 'Food & Beverage', 'job_role': 'F&B Staff',
     'base_staff': 15, 'weekend_mult': 1.6, 'location_pool': FB_LOCS},
    {'id': 'TICK', 'department': 'Ticket Sales', 'job_role': 'Ticket Agent',
     'base_staff': 6, 'weekend_mult': 1.8, 'location_pool': TICKET_LOCS[:3]},
    {'id': 'SKPT', 'department': 'Ski Patrol', 'job_role': 'Patroller',
     'base_staff': 10, 'weekend_mult': 1.2, 'location_pool': None},
    {'id': 'GRND', 'department': 'Grounds', 'job_role': 'Groomer',
     'base_staff': 6, 'weekend_mult': 1.0, 'location_pool': None},
]

# =============================================================================
# ADDITIONAL CONSTANTS FOR NEW TABLES
# =============================================================================
INSTRUCTOR_IDS = [f'INST{str(i).zfill(3)}' for i in range(1, 26)]
PARKING_LOT_IDS = ['PARK001', 'PARK002', 'PARK003', 'PARK004', 'PARK005']

PARKING_LOT_INFO = {
    'PARK001': {'name': 'Main Lot', 'capacity': 500},
    'PARK002': {'name': 'Overflow Lot', 'capacity': 300},
    'PARK003': {'name': 'Village Lot', 'capacity': 200},
    'PARK004': {'name': 'Employee Lot', 'capacity': 150},
    'PARK005': {'name': 'Remote Lot', 'capacity': 100}
}

TRAIL_NAMES = [
    'Summit Run', 'Eagle Ridge', 'Blue Bird', 'Powder Bowl', 'Family Way',
    'Black Diamond', 'Mogul Madness', 'Cruiser', 'North Face', 'Glade Runner',
    'Sunrise', 'Sunset Strip', 'Timberline', 'Snowflake', 'Avalanche'
]

LESSON_TYPES = ['beginner_group', 'intermediate_group', 'advanced_group', 'private', 'kids_camp']
INCIDENT_TYPES = ['collision', 'fall', 'equipment_failure', 'medical', 'lost_skier', 'lift_issue']
INCIDENT_SEVERITY = ['minor', 'moderate', 'serious']

# =============================================================================
# SEASONAL MODIFIERS
# =============================================================================
SEASON_MULTIPLIERS = {11: 0.5, 12: 1.2, 1: 1.5, 2: 1.4, 3: 1.1, 4: 0.7}

def get_daily_modifier(date, rng_instance=None):
    """
    Calculate all modifiers for a single date.
    Returns dict with season_mult, holiday_mult, weather data, etc.
    """
    if rng_instance is None:
        rng_instance = rng

    month = date.month
    day_of_week = date.weekday()
    day = date.day

    # Season multiplier (0 = off-season)
    season_mult = SEASON_MULTIPLIERS.get(month, 0)

    # Holiday multiplier
    holiday_mult = 1.0
    if month == 12 and day >= 20:
        holiday_mult = 2.5
    elif month == 1 and day <= 5:
        holiday_mult = 2.5
    elif month == 2 and 15 <= day <= 21:
        holiday_mult = 1.8

    is_weekend = day_of_week >= 5
    is_saturday = day_of_week == 5

    # Weather simulation
    mean_snow = MONTHLY_SNOWFALL_MEAN.get(month, 0)
    snowfall = max(0.0, rng_instance.normal(mean_snow, 3.0)) if month in [11, 12, 1, 2, 3, 4] else 0
    is_powder_day = snowfall >= 6.0
    storm_warning = snowfall >= 12.0

    # Temperature
    base_temp = MONTHLY_BASE_TEMP.get(month, 30)
    temp_high = base_temp + int(rng_instance.integers(0, 10))
    temp_low = base_temp - int(rng_instance.integers(5, 15))

    return {
        'season_mult': season_mult,
        'holiday_mult': holiday_mult,
        'is_weekend': is_weekend,
        'is_saturday': is_saturday,
        'is_powder_day': is_powder_day,
        'storm_warning': storm_warning,
        'snowfall': snowfall,
        'temp_high_f': temp_high,
        'temp_low_f': temp_low,
        'powder_boost': 1.35 if is_powder_day else 1.0
    }


def get_snow_condition(snowfall, month):
    """Determine snow condition based on snowfall and month."""
    if snowfall >= 6:
        return 'Fresh Snow'
    elif snowfall >= 2:
        return 'Groomed'
    elif month in [3, 4]:
        return 'Spring Conditions'
    else:
        return 'Packed Powder'


def calculate_wait_time(n_visitors, lift_assignments, hours, daily_mod, rng_instance=None):
    """
    Calculate realistic wait times based on:
    - Number of visitors
    - Lift capacity and popularity
    - Time of day
    - Weather/staffing conditions
    """
    if rng_instance is None:
        rng_instance = rng

    total_scans = len(lift_assignments)

    # Get lift metrics
    lift_pop_array = np.array([LIFT_POPULARITY[lid] for lid in LIFT_IDS])
    lift_capacities = np.array([LIFT_CAPACITY[lid] for lid in lift_assignments])
    lift_popularities = np.array([LIFT_POPULARITY[lid] for lid in lift_assignments])

    # Time-based queue factor (peak 10am-1pm)
    time_queue_factor = np.where((hours >= 10) & (hours <= 12), 0.60, 0.40)

    # Queue estimation
    total_lift_share = lift_popularities / lift_pop_array.sum()
    estimated_queue = n_visitors * total_lift_share * time_queue_factor

    # Staffing efficiency
    staffing_efficiency = 0.85 if not daily_mod['is_weekend'] else 0.75
    if daily_mod['storm_warning']:
        staffing_efficiency *= 0.6

    effective_throughput = (lift_capacities / 60) * staffing_efficiency

    # Base wait time
    base_wait = estimated_queue / np.clip(effective_throughput, 1, None)

    # Multipliers
    weekend_mult = rng_instance.uniform(1.2, 1.5) if daily_mod['is_weekend'] else 1.0
    powder_mult = rng_instance.uniform(1.1, 1.3) if daily_mod['is_powder_day'] else 1.0
    holiday_mult = 1.0 + (daily_mod['holiday_mult'] - 1.0) * 0.3

    # Final calculation with noise
    wait_times = base_wait * weekend_mult * powder_mult * holiday_mult
    wait_times = wait_times + rng_instance.normal(0, 2.0, total_scans)
    wait_times = np.clip(wait_times, 1, 45)
    wait_times = np.round(wait_times, 1)

    return wait_times
