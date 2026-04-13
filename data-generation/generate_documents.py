"""
Generate unstructured documents for Cortex Search.
Creates realistic business documents that reference actual ski resort data.

Documents include:
- Safety & Operations guides
- Business/earnings reports
- Customer-facing policies
- Employee handbooks

All documents reference actual lifts, trails, zones, and personas from shared.py.
"""

import json
from datetime import datetime
from config import DATABASE, WAREHOUSE, DOCS_SCHEMA
from shared import (
    LIFT_CAPACITY, LIFT_POPULARITY, WEATHER_ZONES, TRAIL_NAMES,
    STAFFING_DEPARTMENTS, PERSONAS, PERSONA_DISTRIBUTION,
    PARKING_LOT_INFO, LESSON_TYPES, INCIDENT_TYPES
)

# Lift names mapped to IDs (for document references)
LIFT_NAMES = {
    'L001': 'Summit Express Gondola',
    'L002': 'Eagle Ridge 6-Pack',
    'L003': 'Blue Sky Quad',
    'L004': 'Family Fun Quad',
    'L005': 'Black Diamond Chair',
    'L006': 'Sunshine Quad',
    'L007': 'Backbowl Access Chair',
    'L008': 'North Face Chair',
    'L009': 'Terrain Park Express',
    'L010': 'Mid-Mountain Quad',
    'L011': 'Expert Chutes Chair',
    'L012': 'Powder Bowl Chair',
    'L013': 'East Side Quad',
    'L014': 'South Ridge Quad',
    'L015': 'Magic Carpet',
    'L016': 'Learning Area Lift',
    'L017': 'Cruiser 6-Pack',
    'L018': 'Backcountry Gate Access',
}


def generate_documents():
    """Generate all resort documents."""
    documents = []

    # =========================================================================
    # SAFETY & OPERATIONS DOCUMENTS
    # =========================================================================

    documents.append({
        'doc_id': 'SAFETY-001',
        'doc_type': 'safety',
        'title': 'Mountain Safety Guide',
        'content': f"""# Mountain Safety Guide

## Overview
Welcome to Alpine Peaks Resort! Your safety is our top priority. This guide covers essential information for a safe day on the mountain.

## Weather Zones
Our mountain is divided into four weather zones, each with unique conditions:

- **Summit Peak** (Elevation 11,500ft): Exposed to high winds, always check conditions before heading up via {LIFT_NAMES['L001']}.
- **North Ridge** (Elevation 10,800ft): North-facing slopes hold snow longer but can be icy in afternoon.
- **Alpine Bowl** (Elevation 10,200ft): Protected bowl with consistent conditions, accessed via {LIFT_NAMES['L007']}.
- **Village Base** (Elevation 8,500ft): Warmest zone, best for beginners using {LIFT_NAMES['L015']} and {LIFT_NAMES['L016']}.

## Trail Difficulty Ratings
- 🟢 **Green Circle**: Beginner - {', '.join(TRAIL_NAMES[:3])}
- 🔵 **Blue Square**: Intermediate - {', '.join(TRAIL_NAMES[3:8])}
- ⚫ **Black Diamond**: Expert - {', '.join(TRAIL_NAMES[8:12])}
- ⚫⚫ **Double Black**: Experts Only - {', '.join(TRAIL_NAMES[12:])}

## Lift Safety
- Always lower the safety bar when riding {LIFT_NAMES['L001']} (gondola) or any chairlift.
- Watch for download announcements on {LIFT_NAMES['L001']} during high winds.
- {LIFT_NAMES['L018']} (Backcountry Gate) requires avalanche safety gear and partner.

## Emergency Contacts
- Ski Patrol Emergency: Dial 911 from any lift or use orange emergency phones
- Non-emergency: Visit any Ski Patrol station
- Lost children: Report immediately to Guest Services at Village Base

## Your Responsibility Code
1. Always stay in control and be able to stop or avoid other people or objects.
2. People ahead of you have the right of way.
3. Do not stop where you obstruct a trail or are not visible from above.
4. Before starting downhill or merging, look uphill and yield.
5. If you are involved in or witness a collision, remain at the scene.
6. Always use devices to help prevent runaway equipment.
7. Observe all posted signs and warnings.

*Last Updated: {datetime.now().strftime('%B %Y')}*
""",
        'source_file': 'mountain_safety_guide.md'
    })

    documents.append({
        'doc_id': 'SAFETY-002',
        'doc_type': 'safety',
        'title': 'Avalanche Safety Protocol',
        'content': f"""# Avalanche Safety Protocol

## Controlled Avalanche Terrain
Alpine Peaks Resort conducts daily avalanche control in the following areas:
- Alpine Bowl (accessed via {LIFT_NAMES['L007']})
- North Face (accessed via {LIFT_NAMES['L008']})
- Expert Chutes (accessed via {LIFT_NAMES['L011']})
- Powder Bowl (accessed via {LIFT_NAMES['L012']})

## Backcountry Access Policy
{LIFT_NAMES['L018']} provides access to uncontrolled backcountry terrain.

**Required Equipment:**
- Avalanche transceiver (beacon) - turned ON and tested
- Probe (at least 240cm)
- Shovel (metal blade)
- Partner (never travel alone)

**Before Exiting the Gate:**
1. Check current avalanche forecast at SkiPatrol.com/avalanche
2. Register at the Backcountry Gate kiosk
3. Confirm beacon check with Ski Patrol
4. Expected return time logged

## Avalanche Danger Levels
| Level | Color | Description | Recommendation |
|-------|-------|-------------|----------------|
| Low | Green | Generally stable | Normal caution |
| Moderate | Yellow | Heightened conditions | Careful route selection |
| Considerable | Orange | Dangerous conditions | Conservative terrain |
| High | Red | Very dangerous | Avoid steep terrain |
| Extreme | Black | Avoid all avalanche terrain | Stay in bounds |

## Emergency Response
If caught in avalanche:
1. Try to escape to the side
2. Discard poles, fight to stay on surface
3. Create air pocket before burial
4. Stay calm, conserve oxygen

If partner is buried:
1. Watch the victim - note last seen point
2. Call Ski Patrol immediately: 911
3. Turn all beacons to SEARCH mode
4. Begin systematic search from last seen point

## Daily Control Schedule
Avalanche control work typically occurs between 6:00 AM - 8:00 AM. Delayed openings for Alpine Bowl and North Face areas should be expected after significant snowfall (6+ inches).

*Ski Patrol: Your safety partners on the mountain*
""",
        'source_file': 'avalanche_safety_protocol.md'
    })

    documents.append({
        'doc_id': 'OPS-001',
        'doc_type': 'operations',
        'title': 'Lift Operations Manual Summary',
        'content': f"""# Lift Operations Manual - Summary

## Lift Fleet Overview
Alpine Peaks operates 18 lifts with combined capacity of {sum(LIFT_CAPACITY.values()):,} riders per hour.

### High-Capacity Lifts (Primary Circulation)
| Lift | Name | Capacity/Hour | Notes |
|------|------|---------------|-------|
| L001 | {LIFT_NAMES['L001']} | {LIFT_CAPACITY['L001']:,} | Primary summit access, enclosed |
| L002 | {LIFT_NAMES['L002']} | {LIFT_CAPACITY['L002']:,} | High-speed detachable |
| L017 | {LIFT_NAMES['L017']} | {LIFT_CAPACITY['L017']:,} | Primary intermediate terrain |

### Beginner Area Lifts
| Lift | Name | Capacity/Hour | Notes |
|------|------|---------------|-------|
| L015 | {LIFT_NAMES['L015']} | {LIFT_CAPACITY['L015']:,} | Surface lift, first-timers |
| L016 | {LIFT_NAMES['L016']} | {LIFT_CAPACITY['L016']:,} | Beginner chair, slow speed |
| L004 | {LIFT_NAMES['L004']} | {LIFT_CAPACITY['L004']:,} | Family-friendly progression |

### Expert Terrain Access
| Lift | Name | Capacity/Hour | Notes |
|------|------|---------------|-------|
| L005 | {LIFT_NAMES['L005']} | {LIFT_CAPACITY['L005']:,} | Expert terrain |
| L011 | {LIFT_NAMES['L011']} | {LIFT_CAPACITY['L011']:,} | Double-black terrain |
| L018 | {LIFT_NAMES['L018']} | {LIFT_CAPACITY['L018']:,} | Backcountry gate - special protocols |

## Operating Hours
- **Regular Season**: 9:00 AM - 4:00 PM
- **Holiday Periods**: 8:30 AM - 4:30 PM
- **{LIFT_NAMES['L001']}**: 8:45 AM - 4:15 PM (extended for download)

## Wind Hold Protocols
Lifts are placed on wind hold when sustained winds exceed:
- {LIFT_NAMES['L001']} (Gondola): 45 mph
- High-speed detachables (L002, L017): 35 mph
- Fixed-grip chairs: 50 mph
- {LIFT_NAMES['L015']} (Magic Carpet): 25 mph

## Staffing Requirements
Per shift, minimum staffing:
- Load station: 2 operators
- Unload station: 1 operator
- Line management: 1 per 500 riders/hour capacity
- Roving/backup: 1 per 3 lifts

Total Lift Operations staff: {[d for d in STAFFING_DEPARTMENTS if d['id'] == 'LIFT'][0]['base_staff']} base, scaling to {int([d for d in STAFFING_DEPARTMENTS if d['id'] == 'LIFT'][0]['base_staff'] * 1.3)} on peak weekends.

## Daily Checklist
Morning (before opening):
1. Complete full line check
2. Test all safety systems
3. Verify communication systems
4. Check wind speed readings
5. Coordinate with Ski Patrol for sweep assignments

*Reference full manual for detailed procedures*
""",
        'source_file': 'lift_operations_manual.md'
    })

    documents.append({
        'doc_id': 'OPS-002',
        'doc_type': 'operations',
        'title': 'Weather Closure Policy',
        'content': f"""# Weather Closure Policy

## Overview
Alpine Peaks Resort prioritizes guest and employee safety. This policy outlines closure criteria and communication procedures.

## Closure Triggers

### Wind Closures
| Condition | Action |
|-----------|--------|
| Sustained 35+ mph | High-speed lifts on hold ({LIFT_NAMES['L002']}, {LIFT_NAMES['L017']}) |
| Sustained 45+ mph | {LIFT_NAMES['L001']} gondola closed |
| Sustained 50+ mph | All upper mountain closed (Summit Peak, North Ridge) |
| Sustained 60+ mph | Full mountain closure |

### Visibility Closures
| Visibility | Action |
|------------|--------|
| < 100 feet | Expert terrain closed (trails: {', '.join(TRAIL_NAMES[8:12])}) |
| < 50 feet | Upper mountain closed |
| < 25 feet | Full closure except Village Base |

### Lightning/Thunder
Any thunder or lightning within 10 miles triggers immediate evacuation of all exposed lifts.

## Partial Closure Zones
When conditions warrant partial closure:

1. **Zone 1 (Village Base)** - Last to close, first to open
   - {LIFT_NAMES['L015']}, {LIFT_NAMES['L016']}, {LIFT_NAMES['L004']}

2. **Zone 2 (Mid-Mountain)** - Intermediate terrain
   - {LIFT_NAMES['L010']}, {LIFT_NAMES['L006']}, {LIFT_NAMES['L013']}

3. **Zone 3 (Upper Mountain)** - First to close
   - {LIFT_NAMES['L001']}, {LIFT_NAMES['L002']}, {LIFT_NAMES['L007']}

## Guest Communication
Closure announcements via:
- Digital signs at all lift bases
- Resort app push notifications
- Resort website and social media
- In-lodge PA announcements
- Ski Patrol at affected lift lines

## Refund/Credit Policy
See Guest Services Policy DOC-POL-003 for weather-related refund guidelines.

*Safety is non-negotiable. When in doubt, we close.*
""",
        'source_file': 'weather_closure_policy.md'
    })

    # =========================================================================
    # BUSINESS DOCUMENTS
    # =========================================================================

    documents.append({
        'doc_id': 'BIZ-001',
        'doc_type': 'business',
        'title': 'Q4 2024 Earnings Summary',
        'content': f"""# Q4 2024 Earnings Summary
## Alpine Peaks Resort - Internal Document

### Executive Summary
Q4 2024 (October - December) represents the start of our 2024-25 ski season. Early season conditions and strategic pricing initiatives drove strong results.

### Revenue Performance

| Segment | Q4 2024 | Q4 2023 | YoY Change |
|---------|---------|---------|------------|
| Lift Tickets | $4.2M | $3.8M | +10.5% |
| Season Passes | $6.8M | $6.1M | +11.5% |
| Rentals | $1.9M | $1.7M | +11.8% |
| Food & Beverage | $2.4M | $2.2M | +9.1% |
| Ski School | $1.1M | $0.9M | +22.2% |
| **Total** | **$16.4M** | **$14.7M** | **+11.6%** |

### Key Metrics
- **Total Skier Visits**: 142,000 (vs 128,000 Q4 2023)
- **Revenue per Visit**: $115.49 (vs $114.84)
- **Season Pass Holders**: 8,200 (+15% from last year)
- **Pass Holder Visit Rate**: 4.2 visits/holder in Q4

### Customer Mix Analysis
Our customer segments showed healthy distribution:
- Season Pass Holders: {int(PERSONA_DISTRIBUTION['local_pass_holder']*100)}%
- Weekend Warriors: {int(PERSONA_DISTRIBUTION['weekend_warrior']*100)}%
- Vacation Families: {int(PERSONA_DISTRIBUTION['vacation_family']*100)}%
- Day Trippers: {int(PERSONA_DISTRIBUTION['day_tripper']*100)}%
- Other: {int((PERSONA_DISTRIBUTION['expert_skier'] + PERSONA_DISTRIBUTION['group_corporate'] + PERSONA_DISTRIBUTION['beginner'])*100)}%

### Operational Highlights
- **Terrain Open**: 85% by December 15 (earliest in 5 years)
- **Snowmaking**: 320 hours, excellent base established
- **Lift Uptime**: 97.2% (target: 95%)
- **Customer Satisfaction**: 4.6/5.0

### Challenges
- December 8-10 wind event closed {LIFT_NAMES['L001']} for 2 days (-$180K revenue impact)
- Staffing gaps in F&B during holiday week (overtime costs +$45K)

### Q1 2025 Outlook
- Holiday week (Dec 21 - Jan 5) fully booked
- Season pass renewals tracking +18% YoY
- New {LIFT_NAMES['L009']} terrain park features driving youth market

*Prepared by Finance Team - Confidential*
""",
        'source_file': 'q4_2024_earnings.md'
    })

    documents.append({
        'doc_id': 'BIZ-002',
        'doc_type': 'business',
        'title': 'Season Pass Value Analysis',
        'content': f"""# Season Pass Value Analysis
## Making the Case for Pass Holder Growth

### Current Pricing Structure
| Pass Type | Price | Break-Even Visits |
|-----------|-------|-------------------|
| Adult Season Pass | $899 | 7 visits |
| Early Bird Pass | $699 | 5.4 visits |
| Family 4-Pack | $2,999 | 6 visits/person |
| College Pass | $549 | 4.3 visits |
| Senior Pass | $699 | 7 visits |

### Pass Holder Behavior Data
Based on analysis of our {int(PERSONA_DISTRIBUTION['local_pass_holder']*8000):,} local pass holders:

- **Average Visits per Season**: 32 days
- **Average F&B Spend per Visit**: $28
- **Rental Probability**: {int(PERSONAS['local_pass_holder']['rental_prob']*100)}%
- **Laps per Day**: {PERSONAS['local_pass_holder']['laps_range'][0]}-{PERSONAS['local_pass_holder']['laps_range'][1]}

### Total Lifetime Value Comparison
| Segment | Ticket Revenue | F&B Revenue | Other | LTV (3 year) |
|---------|---------------|-------------|-------|--------------|
| Pass Holder | $899/yr | $896/yr | $150/yr | $5,835 |
| Day Tripper | $387/yr | $60/yr | $180/yr | $1,881 |
| Weekend Warrior | $1,290/yr | $420/yr | $200/yr | $5,730 |

### Strategic Recommendations
1. **Early Bird Window Extension**: Extend early bird pricing 2 weeks to capture holiday purchasers
2. **Add-On Bundles**: Offer F&B credits ($100 for $80) at pass purchase
3. **Referral Program**: $50 credit for each new pass holder referral
4. **Conversion Path**: 3-day pass purchasers get $100 off season pass

### Target: 40% Pass Holder Mix
Current: 35% of visits from pass holders
Goal: 40% by 2025-26 season

This would:
- Increase recurring revenue by $1.2M
- Improve visit predictability
- Reduce ticket window staffing needs
- Drive higher per-visit ancillary spending

*Analysis by Marketing & Revenue Team*
""",
        'source_file': 'season_pass_analysis.md'
    })

    documents.append({
        'doc_id': 'BIZ-003',
        'doc_type': 'business',
        'title': 'Strategic Plan 2025-2027 Summary',
        'content': f"""# Strategic Plan 2025-2027
## Alpine Peaks Resort - Executive Summary

### Vision
To be the premier family-friendly ski destination in the region, known for exceptional guest experience, operational excellence, and sustainable mountain practices.

### Strategic Pillars

#### 1. Guest Experience Excellence
**Goal**: Achieve NPS of 70+ (currently 58)

Initiatives:
- Reduce lift wait times to <8 min average (currently 12 min)
- Launch mobile app with real-time wait times for all 18 lifts
- Expand {LIFT_NAMES['L004']} capacity for family terrain
- Add 3 new restaurants with 400 additional seats

#### 2. Revenue Diversification
**Goal**: Grow non-ticket revenue to 45% of total (currently 38%)

Initiatives:
- Expand ski school capacity: {len(LESSON_TYPES)} lesson types, 25 instructors → 35 instructors
- Premium rental tier with demo equipment
- Private event venue at Summit Lodge
- Summer operations: hiking, biking, concerts

#### 3. Operational Efficiency
**Goal**: Reduce cost per skier visit by 8%

Initiatives:
- RFID gate automation (reduce ticket staff by 30%)
- Dynamic pricing optimization
- Predictive maintenance for lift fleet
- Energy efficiency upgrades ($200K annual savings target)

#### 4. Sustainability Leadership
**Goal**: Carbon neutral by 2030

Initiatives:
- 100% renewable energy for snowmaking
- Electric grooming fleet transition (5 of 12 groomers by 2027)
- Zero-waste dining program
- Tree planting partnership (1 tree per season pass sold)

### Financial Targets
| Metric | FY2024 | FY2027 Target | CAGR |
|--------|--------|---------------|------|
| Revenue | $52M | $68M | 9.4% |
| EBITDA | $12M | $18M | 14.5% |
| Skier Visits | 485K | 580K | 6.2% |
| Pass Holders | 8,200 | 12,000 | 13.5% |

### Capital Investment Plan
- **Year 1**: {LIFT_NAMES['L002']} modernization ($4.5M)
- **Year 2**: Base area expansion ($8M)
- **Year 3**: New beginner terrain development ($3M)

*Board Approved: October 2024*
""",
        'source_file': 'strategic_plan_2025_2027.md'
    })

    # =========================================================================
    # CUSTOMER-FACING POLICIES
    # =========================================================================

    documents.append({
        'doc_id': 'POL-001',
        'doc_type': 'policy',
        'title': 'Season Pass Terms and Conditions',
        'content': f"""# Season Pass Terms and Conditions
## 2024-2025 Season

### Pass Benefits
Your Alpine Peaks Season Pass includes:
- Unlimited skiing/riding during operating hours
- No blackout dates
- 10% discount at all resort restaurants
- 15% discount on equipment rentals
- Priority access to ski school booking
- Free parking in {list(PARKING_LOT_INFO.keys())[0]} ({PARKING_LOT_INFO['PARK001']['name']})

### Operating Season
The 2024-2025 season runs from approximately November 15, 2024 through April 15, 2025, conditions permitting. Opening and closing dates are not guaranteed.

### Weather & Closure Policy
- Pass is non-refundable regardless of weather conditions
- No credits for days mountain is closed
- Partial operations (some lifts closed) do not qualify for credits
- Pass Holder Insurance available at purchase (+$89) covers injury-related non-use

### Photo ID Requirement
Your pass includes biometric photo verification. You must:
- Present valid photo ID at time of pickup
- Complete photo registration before first use
- Report lost/stolen passes within 24 hours ($50 replacement fee)

### Prohibited Activities
Pass may be revoked without refund for:
- Reckless skiing/riding endangering others
- Skiing closed terrain or ducking ropes
- Fraudulent pass use (lending to others)
- Violation of resort policies

### Assumption of Risk
By purchasing and using this pass, you acknowledge that skiing and snowboarding are inherently dangerous activities. See full liability waiver at pickup.

### Refund Policy
- **Before season start**: Full refund minus $50 processing fee
- **After season start**: No refunds
- **Pass Holder Insurance**: Covers documented injury preventing use (up to 80% pro-rated refund)

### Contact Information
- Guest Services: 1-800-SKI-ALPS
- Email: passes@alpinepeaks.com
- In person: Ticket Office at {PARKING_LOT_INFO['PARK001']['name']} base

*Terms subject to change. Visit alpinepeaks.com for current policies.*
""",
        'source_file': 'season_pass_terms.md'
    })

    documents.append({
        'doc_id': 'POL-002',
        'doc_type': 'policy',
        'title': 'Equipment Rental Guide',
        'content': f"""# Equipment Rental Guide
## Alpine Peaks Rental Center

### Rental Locations
We have {len(['LOC001', 'LOC002', 'LOC003', 'LOC004', 'LOC005', 'LOC006'])} convenient rental locations:

1. **Village Base Rental** (LOC001) - Main location, largest selection
2. **East Lodge Rental** (LOC002) - Quick pickup for online reservations
3. **Summit Rental** (LOC003) - Demo skis and high-performance gear
4. **Family Center Rental** (LOC004) - Specializes in kids equipment
5. **Terrain Park Shop** (LOC005) - Snowboards and freestyle gear
6. **Quick Rental Express** (LOC006) - 15-minute guarantee or 20% off

### Package Options

| Package | Includes | Adult | Child (12 & under) |
|---------|----------|-------|---------------------|
| Basic | Skis, boots, poles | $55/day | $35/day |
| Performance | Demo skis, boots, poles | $75/day | $45/day |
| Premium | Top demo skis, custom boot fit | $95/day | N/A |
| Snowboard | Board, boots | $60/day | $40/day |
| Helmet Add-on | Helmet only | $15/day | $10/day |

### Size & Fit Guide
**Ski Length**:
- Beginners: Chin to nose height
- Intermediate: Nose to forehead height
- Advanced: Forehead to top of head

**Boot Fit**:
- Should be snug but not painful
- Toes should lightly touch the front
- Heel should not lift when flexing forward

### Reservation Policy
- **Online (48+ hours ahead)**: 15% discount
- **Same-day**: Subject to availability
- **Season lease**: 30% off daily rate equivalent

### Return Policy
- Equipment must be returned by 4:30 PM on final day
- Late returns: Charged additional full day
- Damage beyond normal wear: Assessed at return
- Lost equipment: Full replacement value

### Tips for First-Timers
1. Arrive 30 minutes before lesson time for fitting
2. Wear thin ski socks (we sell them!)
3. Consider lesson + rental package (save 10%)
4. Kids grow fast - season lease often better value

*Pre-book online at alpinepeaks.com/rentals*
""",
        'source_file': 'rental_guide.md'
    })

    documents.append({
        'doc_id': 'POL-003',
        'doc_type': 'policy',
        'title': 'Refund and Credit Policy',
        'content': f"""# Refund and Credit Policy
## Guest Services Guidelines

### Lift Ticket Refunds

| Situation | Resolution |
|-----------|------------|
| Full mountain closure before noon | Full refund or future credit |
| Full mountain closure after noon | 50% credit for future visit |
| Partial closure (some lifts operating) | No refund |
| Personal illness/injury before use | Full refund with documentation |
| Personal illness/injury during use | Pro-rated credit |
| Weather not to guest preference | No refund |

### Processing Timeframes
- Credit applied to account: Same day
- Refund to credit card: 5-7 business days
- Refund by check: 2-3 weeks

### Lesson Cancellations

| Timing | Policy |
|--------|--------|
| 48+ hours before | Full refund |
| 24-48 hours before | 50% refund or full credit |
| Less than 24 hours | No refund, credit at manager discretion |
| Instructor cancellation | Full refund or reschedule priority |

### Rental Cancellations
- Unused equipment returned within 2 hours: Full refund
- Unused equipment returned same day: 75% refund
- Used equipment: No refund

### Season Pass Considerations
Season passes are non-refundable after first use. See Pass Holder Insurance option for coverage.

### How to Request
1. **In Person**: Guest Services desk at Village Base
2. **Phone**: 1-800-SKI-ALPS (hold times vary)
3. **Online**: alpinepeaks.com/guest-services
4. **Email**: refunds@alpinepeaks.com (allow 48 hours response)

### Documentation Required
- Original receipt or order confirmation
- Photo ID matching purchaser
- Medical documentation (for injury claims)
- Incident report number (if applicable)

### Manager Override Authority
Guest Services managers have authority to provide credits up to $500 for exceptional circumstances. Higher amounts require Director approval.

*We want you to return - let us make it right!*
""",
        'source_file': 'refund_policy.md'
    })

    # =========================================================================
    # EMPLOYEE/HR DOCUMENTS
    # =========================================================================

    documents.append({
        'doc_id': 'HR-001',
        'doc_type': 'employee',
        'title': 'Employee Handbook Summary',
        'content': f"""# Employee Handbook Summary
## Alpine Peaks Resort - 2024-2025 Season

### Welcome
Welcome to the Alpine Peaks team! This summary covers key policies. Full handbook available on the employee portal.

### Departments
Alpine Peaks operates with {len(STAFFING_DEPARTMENTS)} core departments:

{chr(10).join([f"- **{d['department']}** ({d['job_role']}s): Base staff {d['base_staff']}, peak {int(d['base_staff'] * d['weekend_mult'])}" for d in STAFFING_DEPARTMENTS])}

### Work Schedule
- **Regular shifts**: 7:00 AM - 3:30 PM or 10:30 AM - 7:00 PM
- **Shift differential**: +$2/hr for early morning (before 7 AM)
- **Weekend premium**: +$1.50/hr for Saturday/Sunday
- **Holiday premium**: +$3/hr for recognized holidays

### Overtime Policy
- Overtime begins after 40 hours/week
- Rate: 1.5x regular hourly rate
- Overtime must be pre-approved by department supervisor
- Peak periods (holidays) may require mandatory overtime with 72-hour notice

### Employee Benefits
**All Employees**:
- Free season pass (after 30 days employment)
- 30% discount on food & beverage
- 50% discount on equipment rental
- Free ski/snowboard lessons (space available)

**Full-Time (32+ hrs/week)**:
- Health insurance (employee + family options)
- 401(k) with 3% match after 1 year
- Paid time off (accrued)
- Employee assistance program

### Attendance Policy
- Call-in required 2+ hours before shift
- No-call/no-show: Written warning (1st), Final warning (2nd), Termination (3rd)
- Excessive tardiness (3+ per month): Disciplinary action

### Safety Requirements
- Safety training completion required within first week
- Incident reporting: ALL incidents must be reported same day
- Personal protective equipment provided by department
- {[d for d in STAFFING_DEPARTMENTS if d['department'] == 'Ski Patrol'][0]['department']}: Additional certifications required

### Employee Parking
- Use {PARKING_LOT_INFO['PARK004']['name']} only ({PARKING_LOT_INFO['PARK004']['capacity']} spaces)
- Display employee parking pass
- Carpooling encouraged - priority parking for 3+ occupants

### Contact HR
- HR Office: Village Base, 2nd Floor
- Email: hr@alpinepeaks.com
- Emergency after-hours: Call Ski Patrol dispatch

*Full policies at employee.alpinepeaks.com*
""",
        'source_file': 'employee_handbook.md'
    })

    documents.append({
        'doc_id': 'HR-002',
        'doc_type': 'employee',
        'title': 'Ski School Instructor Guidelines',
        'content': f"""# Ski School Instructor Guidelines
## Teaching Excellence at Alpine Peaks

### Lesson Types & Ratios
We offer {len(LESSON_TYPES)} lesson formats:

| Type | Max Students | Duration | Terrain |
|------|--------------|----------|---------|
| Beginner Group | 6 | 2 hours | {LIFT_NAMES['L015']}, {LIFT_NAMES['L016']} area |
| Intermediate Group | 8 | 2 hours | {LIFT_NAMES['L004']}, {LIFT_NAMES['L006']} area |
| Advanced Group | 6 | 2 hours | {LIFT_NAMES['L005']}, {LIFT_NAMES['L010']} area |
| Private | 1-5 | 1-4 hours | Customized |
| Kids Camp | 4-6 | Full day | Age-appropriate |

### Instructor Certification Requirements
- PSIA/AASI Level 1: Can teach beginner group
- PSIA/AASI Level 2: Can teach intermediate, assist advanced
- PSIA/AASI Level 3: All lesson types, can mentor
- Children's Specialist: Required for Kids Camp

### Lesson Flow (Group)
1. **Meet & Greet** (10 min): Equipment check, introductions, assess levels
2. **Safety Briefing** (5 min): Trail etiquette, stopping, falling
3. **Warm-up** (10 min): Flat terrain basics
4. **Skill Building** (60 min): Progressive terrain, drills
5. **Free Skiing** (25 min): Apply skills, fun focus
6. **Wrap-up** (10 min): Tips, next steps, photo op

### Teaching Zones by Level
**Beginners**:
- Primary: {TRAIL_NAMES[0]}, {TRAIL_NAMES[1]}
- Lifts: {LIFT_NAMES['L015']}, {LIFT_NAMES['L016']}

**Intermediate**:
- Primary: {TRAIL_NAMES[3]}, {TRAIL_NAMES[4]}, {TRAIL_NAMES[5]}
- Lifts: {LIFT_NAMES['L004']}, {LIFT_NAMES['L006']}, {LIFT_NAMES['L017']}

**Advanced**:
- Primary: {TRAIL_NAMES[8]}, {TRAIL_NAMES[9]}
- Lifts: {LIFT_NAMES['L005']}, {LIFT_NAMES['L010']}

### Compensation Structure
- Base hourly + lesson premium
- Group lesson: +$8/lesson taught
- Private lesson: +$15/lesson taught
- Multi-day clinic: +$25/day
- Tips: Yours to keep, report for taxes

### Incident Protocol
For any student injury or incident:
1. Ensure scene safety
2. Administer first aid (if trained)
3. Radio Ski Patrol immediately
4. Stay with student until Patrol arrives
5. Complete incident report same day
6. Notify Ski School Director

### Guest Experience Tips
- Learn and use student names
- Celebrate small wins enthusiastically
- Take photos for families (ask first!)
- Provide written tips for practice
- Recommend appropriate next steps

*Your passion for skiing creates lifelong skiers!*
""",
        'source_file': 'ski_school_guidelines.md'
    })

    # =========================================================================
    # PRODUCT/SERVICE DESCRIPTIONS
    # =========================================================================

    documents.append({
        'doc_id': 'PROD-001',
        'doc_type': 'product',
        'title': 'Trail Guide and Terrain Overview',
        'content': f"""# Trail Guide & Terrain Overview
## Alpine Peaks Resort - Know Before You Go

### Mountain Statistics
- **Summit Elevation**: 11,500 ft
- **Base Elevation**: 8,500 ft
- **Vertical Drop**: 3,000 ft
- **Skiable Acres**: 2,200
- **Number of Trails**: {len(TRAIL_NAMES)}
- **Number of Lifts**: 18

### Trail Breakdown
| Difficulty | Trails | % of Terrain |
|------------|--------|--------------|
| 🟢 Beginner | {len(TRAIL_NAMES[:3])} | 20% |
| 🔵 Intermediate | {len(TRAIL_NAMES[3:8])} | 35% |
| ⚫ Advanced | {len(TRAIL_NAMES[8:12])} | 30% |
| ⚫⚫ Expert | {len(TRAIL_NAMES[12:])} | 15% |

### Featured Trails

**{TRAIL_NAMES[0]}** 🟢
The classic beginner's run. Wide, gentle slope from {LIFT_NAMES['L016']} with consistent pitch. Perfect for first-timers finding their ski legs.

**{TRAIL_NAMES[4]}** 🟢
Family favorite! Extra-wide cruiser from {LIFT_NAMES['L004']}. Connects to beginner-friendly terrain park features.

**{TRAIL_NAMES[7]}** 🔵
The ultimate intermediate cruiser. Long, rolling terrain off {LIFT_NAMES['L017']}. Groomed nightly, consistently excellent conditions.

**{TRAIL_NAMES[8]}** ⚫
True black diamond experience. Steep, mogul-prone, ungroomed. Access via {LIFT_NAMES['L005']}. Not for the faint of heart!

**{TRAIL_NAMES[13]}** ⚫
Technical steeps with variable snow. Expert-only terrain off {LIFT_NAMES['L011']}.

**{TRAIL_NAMES[14]}** ⚫⚫
Our most challenging inbounds terrain. Avalanche-controlled bowl access via {LIFT_NAMES['L011']}. Requires expert skills.

### Terrain Parks
- **Main Park** ({LIFT_NAMES['L009']}): Progressive features for all levels
- **Mini Park** ({LIFT_NAMES['L004']}): Intro features for beginners
- **Pro Line**: Competition-level jumps and rails (seasonal)

### Recommended Progressions

**Beginner → Intermediate** (Days 1-5):
{TRAIL_NAMES[0]} → {TRAIL_NAMES[1]} → {TRAIL_NAMES[4]} → {TRAIL_NAMES[3]}

**Intermediate → Advanced** (Days 5-10):
{TRAIL_NAMES[7]} → {TRAIL_NAMES[5]} → {TRAIL_NAMES[6]} → {TRAIL_NAMES[8]}

**Advanced → Expert**:
{TRAIL_NAMES[8]} → {TRAIL_NAMES[9]} → {TRAIL_NAMES[12]} → {TRAIL_NAMES[14]}

### Real-Time Conditions
Check alpinepeaks.com/conditions or the Alpine Peaks app for:
- Trail open/closed status
- Grooming report
- Lift wait times
- Snow conditions by zone

*The mountain is waiting - see you on the slopes!*
""",
        'source_file': 'trail_guide.md'
    })

    # =========================================================================
    # HIGH-IMPACT ADDITIONS - Enable Cross-Data Queries
    # =========================================================================

    documents.append({
        'doc_id': 'FEEDBACK-001',
        'doc_type': 'feedback',
        'title': 'December 2024 Guest Feedback Summary',
        'content': f"""# Guest Feedback Summary - December 2024
## Voice of Customer Analysis

### Overall Satisfaction
- **NPS Score**: 58 (Target: 65)
- **Total Responses**: 2,847
- **Response Rate**: 12% of unique visitors

### Top Positive Themes

**1. Snow Conditions (892 mentions)**
> "Best early season conditions in years! {TRAIL_NAMES[3]} was perfectly groomed."
> "Fresh powder in {WEATHER_ZONES[2]} - felt like January skiing in December!"

**2. Staff Friendliness (634 mentions)**
> "Lift operators at {LIFT_NAMES['L004']} were so helpful with my kids."
> "Rental staff at Village Base made fitting quick and painless."

**3. Food Quality (412 mentions)**
> "Summit restaurant exceeded expectations - great views and food!"
> "New grab-and-go options at Mid-Mountain are a game changer."

### Top Negative Themes

**1. Lift Wait Times (723 mentions)** ⚠️ PRIORITY
> "Waited 25 minutes for {LIFT_NAMES['L001']} on Saturday. Unacceptable."
> "{LIFT_NAMES['L010']} lines were brutal from 10am-1pm."
> "Why can't you open more lifts on busy days?"

**Average Reported Wait**: 18 min (vs. 12 min target)
**Peak Complaint Days**: Dec 21-23 (Saturday-Monday holiday week)

**2. Parking Issues (389 mentions)**
> "{PARKING_LOT_INFO['PARK001']['name']} full by 9am - had to park in overflow."
> "Shuttle from {PARKING_LOT_INFO['PARK002']['name']} took 20 minutes."

**3. Rental Availability (267 mentions)**
> "No size 10 boots available at 10am on Saturday."
> "Demo skis sold out - drove 2 hours and couldn't rent performance gear."

### Segment-Specific Feedback

**Season Pass Holders** (NPS: 72)
- Appreciate early morning access
- Want dedicated parking
- Request more expert terrain grooming

**Vacation Families** (NPS: 51) ⚠️
- Frustrated by lesson booking (sold out)
- Kids menu needs more options
- Want family-specific lift lines

**Weekend Warriors** (NPS: 54)
- Cite wait times as #1 issue
- Appreciate grooming quality
- Want real-time wait time app

### Action Items from Feedback
1. **Immediate**: Add signage for alternate lifts when {LIFT_NAMES['L001']} exceeds 15 min wait
2. **Short-term**: Expand rental inventory for size 8-10 boots
3. **Medium-term**: Launch wait time feature in mobile app
4. **Long-term**: {LIFT_NAMES['L010']} capacity upgrade (see Strategic Plan)

### Verbatim Highlights

*"This resort has amazing terrain but the operational execution doesn't match.
I pay $130/day and spend 30% of it in lift lines. Please invest in capacity!"*
— Pass Holder, Dec 22

*"Our family had the BEST ski vacation. Lessons were fantastic,
kids went from pizza to parallel in 3 days. Will definitely return!"*
— Vacation Family, Dec 28

*"Pro tip: ski {TRAIL_NAMES[8]} in the morning before it gets tracked out.
Afternoon crowds on {LIFT_NAMES['L005']} make it not worth it."*
— Expert Skier, Dec 15

*Report compiled by Guest Experience Team*
""",
        'source_file': 'dec_2024_feedback.md'
    })

    documents.append({
        'doc_id': 'MEMO-001',
        'doc_type': 'memo',
        'title': 'Operations Memo - Week of Dec 16, 2024',
        'content': f"""# Weekly Operations Memo
## Week of December 16-22, 2024

**From**: Mountain Operations Director
**To**: All Department Heads
**Date**: December 15, 2024

---

### Weather Outlook
- **Monday-Wednesday**: Clear, temps 18-28°F, light winds
- **Thursday**: Storm arriving, 4-8" expected overnight
- **Friday-Sunday**: Post-storm clearing, POWDER CONDITIONS

⚠️ **Prepare for surge**: Friday will be BUSY. Last year's comparable day saw 4,200 visitors.

### Staffing Adjustments

| Department | Mon-Wed | Thu | Fri-Sun |
|------------|---------|-----|---------|
| Lift Ops | Standard | -10% (weather) | +40% |
| Rentals | Standard | Standard | +50% |
| F&B | Standard | -20% | +60% |
| Ski Patrol | Standard | +20% (avy work) | +30% |

**Key Call-Outs**:
- {LIFT_NAMES['L007']} and {LIFT_NAMES['L012']} delayed opening Thursday for avalanche control
- Extra ticket windows Friday 7:30 AM
- All hands on deck Saturday - cancel non-essential PTO

### Lift Status

| Lift | Status | Notes |
|------|--------|-------|
| {LIFT_NAMES['L001']} | ✅ | New haul rope installed - running smooth |
| {LIFT_NAMES['L002']} | ✅ | Minor drive issue resolved |
| {LIFT_NAMES['L011']} | ⚠️ | Delayed opening Thu for control work |
| {LIFT_NAMES['L018']} | ⚠️ | Backcountry gate closed Thu-Fri AM |

### Operational Priorities

**1. Wait Time Management**
{LIFT_NAMES['L001']} wait times hit 28 min last Saturday. This is unacceptable.
- Deploy line management staff by 9 AM on weekends
- Radio updates every 30 minutes to Dispatch
- Actively redirect guests to {LIFT_NAMES['L002']} and {LIFT_NAMES['L017']}

**2. Rental Pre-staging**
Size 8-10 boots ran out by 10 AM last weekend.
- Pre-stage 50 additional pairs in those sizes
- Online reservation guests get priority pickup

**3. Parking Flow**
{PARKING_LOT_INFO['PARK001']['name']} filled by 8:45 AM Saturday.
- Open {PARKING_LOT_INFO['PARK002']['name']} overflow by 8 AM
- Shuttle service every 10 minutes when overflow active

### Safety Notes

- ICE WARNING: {TRAIL_NAMES[8]} and {TRAIL_NAMES[9]} icy in mornings until grooming
- {WEATHER_ZONES[0]} winds forecast 30+ mph Thursday - prepare for upper mountain hold

### Holiday Week Preview (Dec 21-Jan 5)

This is our biggest revenue period. Every department at 100%.
- Expected daily visitors: 3,500-4,500
- Season pass scan estimate: 1,400/day
- F&B revenue target: $85K/day

**Let's execute flawlessly.**

— Mountain Ops
""",
        'source_file': 'ops_memo_dec16.md'
    })

    documents.append({
        'doc_id': 'MARKETING-001',
        'doc_type': 'marketing',
        'title': 'Powder Alert Campaign - December 2024',
        'content': f"""# Marketing Campaign Brief
## "Powder Alert" Email Campaign - December 2024

### Campaign Overview
**Objective**: Drive incremental visits within 48 hours of significant snowfall
**Target**: All email subscribers within 150-mile radius
**Trigger**: 6+ inches of overnight snowfall

### Campaign Execution - December 19, 2024

**Snowfall Recorded**: 8.2 inches overnight (Dec 18-19)
**Email Sent**: December 19, 2024 at 5:47 AM
**Subject Line**: "🚨 POWDER ALERT: 8 inches overnight at Alpine Peaks!"

**Recipients**: 45,234
**Open Rate**: 52.3% (23,667 opens)
**Click Rate**: 18.7% (4,427 clicks)
**Conversions**: 1,247 ticket purchases within 48 hours

### Email Content Summary

> **FRESH POWDER AWAITS!**
>
> Last night's storm dropped 8.2 inches of fresh snow across the mountain.
>
> **Current Conditions**:
> - {WEATHER_ZONES[0]}: Fresh Snow, 8" new
> - {WEATHER_ZONES[2]}: Fresh Snow, 7" new
> - Base Depth: 42 inches
>
> **Best Powder Runs**:
> - {TRAIL_NAMES[3]} (untracked until 10 AM)
> - {TRAIL_NAMES[9]} (experts only - amazing!)
> - {LIFT_NAMES['L012']} access for {WEATHER_ZONES[2]} stashes
>
> **Book Now**: Day tickets $119 (save $10 with code POWDER24)

### Results Analysis

| Metric | Dec 19 | Dec 20 | 2-Day Total |
|--------|--------|--------|-------------|
| Ticket Sales (Email) | 847 | 400 | 1,247 |
| Revenue (Email) | $100,793 | $47,600 | $148,393 |
| Total Visitors | 3,892 | 4,127 | 8,019 |
| Incremental vs. Forecast | +1,200 | +1,500 | +2,700 |

**Estimated Campaign ROI**:
- Email cost: ~$500
- Incremental revenue: ~$148,000
- ROI: 296x 🎉

### Lessons Learned

**What Worked**:
- 5:47 AM send time (before commute decisions)
- Specific trail recommendations drove engagement
- Discount code created urgency

**Improvements for Next Time**:
- Add real-time lift wait estimates
- Segment by distance (closer = faster send)
- Test "Powder + Rentals" bundle offer

### Related Campaigns

| Date | Trigger | Results |
|------|---------|---------|
| Dec 5 | 6" snowfall | 892 conversions |
| Dec 12 | 4" snowfall | 634 conversions (lower - threshold too low?) |
| Dec 19 | 8" snowfall | 1,247 conversions |
| Jan 3 | 10" snowfall | (Pending) |

**Recommendation**: Maintain 6" trigger threshold. 4" did not drive sufficient urgency.

*Campaign managed by Digital Marketing Team*
""",
        'source_file': 'powder_alert_campaign.md'
    })

    documents.append({
        'doc_id': 'FAQ-001',
        'doc_type': 'faq',
        'title': 'Frequently Asked Questions',
        'content': f"""# Frequently Asked Questions
## Alpine Peaks Resort - Guest Services Reference

### Tickets & Passes

**Q: What are your lift ticket prices?**
A: Adult day tickets are $129, child (6-12) $79, senior (65+) $99. Half-day tickets (starting noon) are $89. Book online for best pricing.

**Q: What's included in a season pass?**
A: Season passes include unlimited skiing/riding with no blackout dates, 10% F&B discount, 15% rental discount, priority ski school booking, and free parking in {PARKING_LOT_INFO['PARK001']['name']}.

**Q: What's your refund policy for tickets?**
A: Unused tickets can be refunded up to 48 hours before. If the mountain closes completely before noon, you receive a full credit. Partial closures do not qualify for refunds.

**Q: Do you offer multi-day discounts?**
A: Yes! 3-day passes are $99/day effective, 5-day passes are $89/day effective. Best value is the season pass at $899 (break-even at 7 visits).

### Operations

**Q: What are your operating hours?**
A: Lifts operate 9 AM - 4 PM daily. {LIFT_NAMES['L001']} opens at 8:45 AM and runs until 4:15 PM for download. Holiday periods may have extended hours.

**Q: How many lifts do you have?**
A: We operate 18 lifts with total capacity of {sum(LIFT_CAPACITY.values()):,} riders per hour. Our flagship {LIFT_NAMES['L001']} has {LIFT_CAPACITY['L001']:,}/hour capacity.

**Q: Which lifts are best for beginners?**
A: Start with {LIFT_NAMES['L015']} (Magic Carpet) and {LIFT_NAMES['L016']} (Learning Area). When ready to progress, {LIFT_NAMES['L004']} accesses gentle green terrain.

**Q: What causes lift closures?**
A: High winds (35+ mph for high-speed lifts, 50+ mph for fixed-grip), lightning within 10 miles, or mechanical issues. Check our app for real-time status.

### Weather & Conditions

**Q: What are your different mountain zones?**
A: We have four zones: {', '.join(WEATHER_ZONES)}. Summit Peak (11,500 ft) is coldest/windiest, Village Base (8,500 ft) is warmest and most protected.

**Q: What do the snow condition ratings mean?**
A: Fresh Snow = new powder, Groomed = machine-prepared corduroy, Packed Powder = firm base, Spring Conditions = softer afternoon snow, Variable = mixed conditions.

**Q: Do you make snow?**
A: Yes! We have snowmaking on 60% of terrain including all beginner areas. We typically begin snowmaking in early November when temps allow.

### Rentals & Lessons

**Q: Do I need reservations for rentals?**
A: Reservations aren't required but are strongly recommended, especially weekends and holidays. Book online for 15% discount and guaranteed equipment.

**Q: What's included in a lesson?**
A: Group lessons include 2 hours instruction, lift ticket for designated learning terrain, and equipment if needed. Private lessons can access any terrain.

**Q: Do you have equipment for young children?**
A: Yes! We rent equipment starting at age 3. Our {LIFT_NAMES['L004']} area has a dedicated kids zone.

### Dining & Services

**Q: Where can I eat on the mountain?**
A: We have 10 dining locations: 4 sit-down restaurants, 4 quick-service, and 2 bars. Summit restaurant has the best views!

**Q: Is there WiFi available?**
A: Free WiFi is available in all lodge areas. Coverage does not extend to lifts or trails.

**Q: Do you have lockers?**
A: Day lockers are available at Village Base ($15/day). Season locker rentals available for pass holders ($250/season).

### Safety

**Q: What's the Your Responsibility Code?**
A: It's the skier/rider code of conduct. Key points: stay in control, yield to people ahead, don't stop where you're not visible, look uphill before merging.

**Q: What should I do if there's an accident?**
A: If you witness an incident, stay at the scene, call Ski Patrol (dial 911 from any lift or use orange emergency phones), and don't move an injured person.

**Q: Can I ski out-of-bounds?**
A: {LIFT_NAMES['L018']} provides backcountry access, but you must have avalanche gear (beacon, probe, shovel) and a partner. The gate may be closed during high hazard.

### Contact

**Guest Services**: 1-800-SKI-ALPS
**Website**: alpinepeaks.com
**App**: Search "Alpine Peaks" on iOS/Android

*Can't find your answer? Chat with us in the app or visit any Guest Services desk!*
""",
        'source_file': 'faq.md'
    })

    documents.append({
        'doc_id': 'INCIDENT-001',
        'doc_type': 'incident',
        'title': 'Monthly Incident Summary - December 2024',
        'content': f"""# Monthly Incident Summary
## December 2024 - Ski Patrol Report

### Overview
| Metric | Dec 2024 | Dec 2023 | YoY Change |
|--------|----------|----------|------------|
| Total Incidents | 127 | 142 | -10.6% ✅ |
| Transports to Hospital | 8 | 12 | -33.3% ✅ |
| Skier Days | 89,000 | 82,000 | +8.5% |
| Incident Rate | 1.43/1000 | 1.73/1000 | -17.3% ✅ |

### Incidents by Type
| Type | Count | % of Total | Primary Location |
|------|-------|------------|------------------|
| Falls | 68 | 53.5% | {TRAIL_NAMES[8]}, {TRAIL_NAMES[5]} |
| Collisions | 31 | 24.4% | {TRAIL_NAMES[7]}, {TRAIL_NAMES[4]} |
| Equipment Failure | 12 | 9.4% | Various |
| Medical (non-ski) | 9 | 7.1% | Base Lodge |
| Lift-Related | 4 | 3.1% | {LIFT_NAMES['L004']}, {LIFT_NAMES['L001']} |
| Lost Skier | 3 | 2.4% | {WEATHER_ZONES[1]} |

### Incidents by Severity
- **Minor** (self-transport or released on-scene): 98 (77.2%)
- **Moderate** (toboggan transport to first aid): 21 (16.5%)
- **Serious** (ambulance/hospital): 8 (6.3%)

### High-Profile Incidents

**December 8 - Collision on {TRAIL_NAMES[7]}**
- Two intermediate skiers collided at trail merge
- One transported with suspected ACL injury
- Root cause: Poor visibility from intersection angle
- **Action**: Added signage and slow zone marking

**December 15 - Fall on {TRAIL_NAMES[14]}**
- Expert skier fell in steep chute
- Shoulder injury, transported to hospital
- Contributing factor: Icy conditions after wind event
- **Action**: Enhanced morning grooming rotation

**December 22 - Lift Incident at {LIFT_NAMES['L004']}**
- Child's ski tip caught on loading ramp
- Lift stopped, child assisted, no injury
- Root cause: Improper tip positioning
- **Action**: Additional safety guidance signage at load

### Location Analysis

**Highest Incident Trails**:
1. {TRAIL_NAMES[8]} - 18 incidents (14.2%)
   - Steep pitch, moguls, attracts intermediates beyond ability
2. {TRAIL_NAMES[7]} - 14 incidents (11.0%)
   - High traffic, trail merge point
3. {TRAIL_NAMES[5]} - 12 incidents (9.4%)
   - Variable conditions, sun/shade transitions

**Lowest Incident Trails**:
- {TRAIL_NAMES[0]}, {TRAIL_NAMES[1]} - 2 incidents each
- Beginner terrain well-maintained and appropriately used

### Time of Day Distribution
| Time | Incidents | % |
|------|-----------|---|
| 9-10 AM | 12 | 9.4% |
| 10-11 AM | 18 | 14.2% |
| 11 AM-12 PM | 24 | 18.9% |
| 12-1 PM | 16 | 12.6% |
| 1-2 PM | 22 | 17.3% |
| 2-3 PM | 19 | 15.0% |
| 3-4 PM | 16 | 12.6% |

**Peak Period**: 11 AM - 12 PM (fatigue + crowds)

### Recommendations

1. **Signage Enhancement**: Add "Slow Zone" signs at {TRAIL_NAMES[7]} merge
2. **Grooming Priority**: Morning pass on {TRAIL_NAMES[8]} to address ice
3. **Patrol Positioning**: Station at {TRAIL_NAMES[5]}/6 intersection during peak hours
4. **Guest Education**: App push notification about fatigue after 2+ hours

### Patrol Response Metrics
- Average response time: 4.2 minutes (target: <5 min) ✅
- Toboggan transport time: 8.7 minutes average
- First aid treatment capacity: Never exceeded

*Report prepared by Ski Patrol Director*
*All incidents reported per industry standards (NSAA guidelines)*
""",
        'source_file': 'incident_summary_dec2024.md'
    })

    return documents


def save_documents_json(documents, output_path='documents.json'):
    """Save documents to JSON file for loading to Snowflake."""
    with open(output_path, 'w') as f:
        json.dump(documents, f, indent=2)
    print(f"✅ Saved {len(documents)} documents to {output_path}")
    return output_path


def create_sql_inserts(documents):
    """Generate SQL INSERT statements for documents."""
    _docs_table = f"{DATABASE}.{DOCS_SCHEMA}.RESORT_DOCUMENTS"
    _search_svc = f"{DATABASE}.{DOCS_SCHEMA}.RESORT_DOCS_SEARCH"
    sql = f"""-- Create documents table
CREATE TABLE IF NOT EXISTS {_docs_table} (
    DOC_ID VARCHAR(50) PRIMARY KEY,
    DOC_TYPE VARCHAR(50),
    TITLE VARCHAR(500),
    CONTENT TEXT,
    SOURCE_FILE VARCHAR(200),
    CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- Insert documents
"""

    for doc in documents:
        escaped_content = doc['content'].replace("'", "''")
        sql += f"""
INSERT INTO {_docs_table} (DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE)
VALUES ('{doc['doc_id']}', '{doc['doc_type']}', '{doc['title']}', '{escaped_content}', '{doc['source_file']}');
"""

    sql += f"""
-- Create Cortex Search Service
CREATE OR REPLACE CORTEX SEARCH SERVICE {_search_svc}
  ON CONTENT
  ATTRIBUTES DOC_TYPE, TITLE
  WAREHOUSE = {WAREHOUSE}
  TARGET_LAG = '1 day'
  AS (
    SELECT DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE
    FROM {_docs_table}
  );
"""

    return sql


if __name__ == '__main__':
    print("🎿 Generating ski resort documents...")

    documents = generate_documents()

    print(f"\n📄 Generated {len(documents)} documents:")
    for doc in documents:
        print(f"   [{doc['doc_type']:10}] {doc['title']}")

    # Save to JSON
    save_documents_json(documents, 'documents.json')

    # Generate SQL
    sql = create_sql_inserts(documents)
    with open('load_documents.sql', 'w') as f:
        f.write(sql)
    print(f"✅ Saved SQL to load_documents.sql")

    print("\n📊 Document summary by type:")
    types = {}
    for doc in documents:
        types[doc['doc_type']] = types.get(doc['doc_type'], 0) + 1
    for doc_type, count in sorted(types.items()):
        print(f"   {doc_type}: {count}")
