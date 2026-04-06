-- Create documents table
CREATE TABLE IF NOT EXISTS SKI_RESORT_DB.DOCS.RESORT_DOCUMENTS (
    DOC_ID VARCHAR(50) PRIMARY KEY,
    DOC_TYPE VARCHAR(50),
    TITLE VARCHAR(500),
    CONTENT TEXT,
    SOURCE_FILE VARCHAR(200),
    CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- Insert documents

INSERT INTO SKI_RESORT_DB.DOCS.RESORT_DOCUMENTS (DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE)
VALUES ('SAFETY-001', 'safety', 'Mountain Safety Guide', '# Mountain Safety Guide

## Overview
Welcome to Alpine Peaks Resort! Your safety is our top priority. This guide covers essential information for a safe day on the mountain.

## Weather Zones
Our mountain is divided into four weather zones, each with unique conditions:

- **Summit Peak** (Elevation 11,500ft): Exposed to high winds, always check conditions before heading up via Summit Express Gondola.
- **North Ridge** (Elevation 10,800ft): North-facing slopes hold snow longer but can be icy in afternoon.
- **Alpine Bowl** (Elevation 10,200ft): Protected bowl with consistent conditions, accessed via Backbowl Access Chair.
- **Village Base** (Elevation 8,500ft): Warmest zone, best for beginners using Magic Carpet and Learning Area Lift.

## Trail Difficulty Ratings
- 🟢 **Green Circle**: Beginner - Summit Run, Eagle Ridge, Blue Bird
- 🔵 **Blue Square**: Intermediate - Powder Bowl, Family Way, Black Diamond, Mogul Madness, Cruiser
- ⚫ **Black Diamond**: Expert - North Face, Glade Runner, Sunrise, Sunset Strip
- ⚫⚫ **Double Black**: Experts Only - Timberline, Snowflake, Avalanche

## Lift Safety
- Always lower the safety bar when riding Summit Express Gondola (gondola) or any chairlift.
- Watch for download announcements on Summit Express Gondola during high winds.
- Backcountry Gate Access (Backcountry Gate) requires avalanche safety gear and partner.

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

*Last Updated: December 2025*
', 'mountain_safety_guide.md');

INSERT INTO SKI_RESORT_DB.DOCS.RESORT_DOCUMENTS (DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE)
VALUES ('SAFETY-002', 'safety', 'Avalanche Safety Protocol', '# Avalanche Safety Protocol

## Controlled Avalanche Terrain
Alpine Peaks Resort conducts daily avalanche control in the following areas:
- Alpine Bowl (accessed via Backbowl Access Chair)
- North Face (accessed via North Face Chair)
- Expert Chutes (accessed via Expert Chutes Chair)
- Powder Bowl (accessed via Powder Bowl Chair)

## Backcountry Access Policy
Backcountry Gate Access provides access to uncontrolled backcountry terrain.

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
', 'avalanche_safety_protocol.md');

INSERT INTO SKI_RESORT_DB.DOCS.RESORT_DOCUMENTS (DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE)
VALUES ('OPS-001', 'operations', 'Lift Operations Manual Summary', '# Lift Operations Manual - Summary

## Lift Fleet Overview
Alpine Peaks operates 18 lifts with combined capacity of 19,500 riders per hour.

### High-Capacity Lifts (Primary Circulation)
| Lift | Name | Capacity/Hour | Notes |
|------|------|---------------|-------|
| L001 | Summit Express Gondola | 2,500 | Primary summit access, enclosed |
| L002 | Eagle Ridge 6-Pack | 1,500 | High-speed detachable |
| L017 | Cruiser 6-Pack | 1,500 | Primary intermediate terrain |

### Beginner Area Lifts
| Lift | Name | Capacity/Hour | Notes |
|------|------|---------------|-------|
| L015 | Magic Carpet | 800 | Surface lift, first-timers |
| L016 | Learning Area Lift | 600 | Beginner chair, slow speed |
| L004 | Family Fun Quad | 1,200 | Family-friendly progression |

### Expert Terrain Access
| Lift | Name | Capacity/Hour | Notes |
|------|------|---------------|-------|
| L005 | Black Diamond Chair | 1,000 | Expert terrain |
| L011 | Expert Chutes Chair | 600 | Double-black terrain |
| L018 | Backcountry Gate Access | 400 | Backcountry gate - special protocols |

## Operating Hours
- **Regular Season**: 9:00 AM - 4:00 PM
- **Holiday Periods**: 8:30 AM - 4:30 PM
- **Summit Express Gondola**: 8:45 AM - 4:15 PM (extended for download)

## Wind Hold Protocols
Lifts are placed on wind hold when sustained winds exceed:
- Summit Express Gondola (Gondola): 45 mph
- High-speed detachables (L002, L017): 35 mph
- Fixed-grip chairs: 50 mph
- Magic Carpet (Magic Carpet): 25 mph

## Staffing Requirements
Per shift, minimum staffing:
- Load station: 2 operators
- Unload station: 1 operator
- Line management: 1 per 500 riders/hour capacity
- Roving/backup: 1 per 3 lifts

Total Lift Operations staff: 18 base, scaling to 23 on peak weekends.

## Daily Checklist
Morning (before opening):
1. Complete full line check
2. Test all safety systems
3. Verify communication systems
4. Check wind speed readings
5. Coordinate with Ski Patrol for sweep assignments

*Reference full manual for detailed procedures*
', 'lift_operations_manual.md');

INSERT INTO SKI_RESORT_DB.DOCS.RESORT_DOCUMENTS (DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE)
VALUES ('OPS-002', 'operations', 'Weather Closure Policy', '# Weather Closure Policy

## Overview
Alpine Peaks Resort prioritizes guest and employee safety. This policy outlines closure criteria and communication procedures.

## Closure Triggers

### Wind Closures
| Condition | Action |
|-----------|--------|
| Sustained 35+ mph | High-speed lifts on hold (Eagle Ridge 6-Pack, Cruiser 6-Pack) |
| Sustained 45+ mph | Summit Express Gondola gondola closed |
| Sustained 50+ mph | All upper mountain closed (Summit Peak, North Ridge) |
| Sustained 60+ mph | Full mountain closure |

### Visibility Closures
| Visibility | Action |
|------------|--------|
| < 100 feet | Expert terrain closed (trails: North Face, Glade Runner, Sunrise, Sunset Strip) |
| < 50 feet | Upper mountain closed |
| < 25 feet | Full closure except Village Base |

### Lightning/Thunder
Any thunder or lightning within 10 miles triggers immediate evacuation of all exposed lifts.

## Partial Closure Zones
When conditions warrant partial closure:

1. **Zone 1 (Village Base)** - Last to close, first to open
   - Magic Carpet, Learning Area Lift, Family Fun Quad

2. **Zone 2 (Mid-Mountain)** - Intermediate terrain
   - Mid-Mountain Quad, Sunshine Quad, East Side Quad

3. **Zone 3 (Upper Mountain)** - First to close
   - Summit Express Gondola, Eagle Ridge 6-Pack, Backbowl Access Chair

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
', 'weather_closure_policy.md');

INSERT INTO SKI_RESORT_DB.DOCS.RESORT_DOCUMENTS (DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE)
VALUES ('BIZ-001', 'business', 'Q4 2024 Earnings Summary', '# Q4 2024 Earnings Summary
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
- Season Pass Holders: 15%
- Weekend Warriors: 25%
- Vacation Families: 30%
- Day Trippers: 20%
- Other: 10%

### Operational Highlights
- **Terrain Open**: 85% by December 15 (earliest in 5 years)
- **Snowmaking**: 320 hours, excellent base established
- **Lift Uptime**: 97.2% (target: 95%)
- **Customer Satisfaction**: 4.6/5.0

### Challenges
- December 8-10 wind event closed Summit Express Gondola for 2 days (-$180K revenue impact)
- Staffing gaps in F&B during holiday week (overtime costs +$45K)

### Q1 2025 Outlook
- Holiday week (Dec 21 - Jan 5) fully booked
- Season pass renewals tracking +18% YoY
- New Terrain Park Express terrain park features driving youth market

*Prepared by Finance Team - Confidential*
', 'q4_2024_earnings.md');

INSERT INTO SKI_RESORT_DB.DOCS.RESORT_DOCUMENTS (DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE)
VALUES ('BIZ-002', 'business', 'Season Pass Value Analysis', '# Season Pass Value Analysis
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
Based on analysis of our 1,200 local pass holders:

- **Average Visits per Season**: 32 days
- **Average F&B Spend per Visit**: $28
- **Rental Probability**: 5%
- **Laps per Day**: 15-25

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
', 'season_pass_analysis.md');

INSERT INTO SKI_RESORT_DB.DOCS.RESORT_DOCUMENTS (DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE)
VALUES ('BIZ-003', 'business', 'Strategic Plan 2025-2027 Summary', '# Strategic Plan 2025-2027
## Alpine Peaks Resort - Executive Summary

### Vision
To be the premier family-friendly ski destination in the region, known for exceptional guest experience, operational excellence, and sustainable mountain practices.

### Strategic Pillars

#### 1. Guest Experience Excellence
**Goal**: Achieve NPS of 70+ (currently 58)

Initiatives:
- Reduce lift wait times to <8 min average (currently 12 min)
- Launch mobile app with real-time wait times for all 18 lifts
- Expand Family Fun Quad capacity for family terrain
- Add 3 new restaurants with 400 additional seats

#### 2. Revenue Diversification
**Goal**: Grow non-ticket revenue to 45% of total (currently 38%)

Initiatives:
- Expand ski school capacity: 5 lesson types, 25 instructors → 35 instructors
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
- **Year 1**: Eagle Ridge 6-Pack modernization ($4.5M)
- **Year 2**: Base area expansion ($8M)
- **Year 3**: New beginner terrain development ($3M)

*Board Approved: October 2024*
', 'strategic_plan_2025_2027.md');

INSERT INTO SKI_RESORT_DB.DOCS.RESORT_DOCUMENTS (DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE)
VALUES ('POL-001', 'policy', 'Season Pass Terms and Conditions', '# Season Pass Terms and Conditions
## 2024-2025 Season

### Pass Benefits
Your Alpine Peaks Season Pass includes:
- Unlimited skiing/riding during operating hours
- No blackout dates
- 10% discount at all resort restaurants
- 15% discount on equipment rentals
- Priority access to ski school booking
- Free parking in PARK001 (Main Lot)

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
- In person: Ticket Office at Main Lot base

*Terms subject to change. Visit alpinepeaks.com for current policies.*
', 'season_pass_terms.md');

INSERT INTO SKI_RESORT_DB.DOCS.RESORT_DOCUMENTS (DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE)
VALUES ('POL-002', 'policy', 'Equipment Rental Guide', '# Equipment Rental Guide
## Alpine Peaks Rental Center

### Rental Locations
We have 6 convenient rental locations:

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
', 'rental_guide.md');

INSERT INTO SKI_RESORT_DB.DOCS.RESORT_DOCUMENTS (DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE)
VALUES ('POL-003', 'policy', 'Refund and Credit Policy', '# Refund and Credit Policy
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
', 'refund_policy.md');

INSERT INTO SKI_RESORT_DB.DOCS.RESORT_DOCUMENTS (DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE)
VALUES ('HR-001', 'employee', 'Employee Handbook Summary', '# Employee Handbook Summary
## Alpine Peaks Resort - 2024-2025 Season

### Welcome
Welcome to the Alpine Peaks team! This summary covers key policies. Full handbook available on the employee portal.

### Departments
Alpine Peaks operates with 6 core departments:

- **Lift Operations** (Lift Operators): Base staff 18, peak 23
- **Rentals** (Rental Techs): Base staff 8, peak 12
- **Food & Beverage** (F&B Staffs): Base staff 15, peak 24
- **Ticket Sales** (Ticket Agents): Base staff 6, peak 10
- **Ski Patrol** (Patrollers): Base staff 10, peak 12
- **Grounds** (Groomers): Base staff 6, peak 6

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
- Ski Patrol: Additional certifications required

### Employee Parking
- Use Employee Lot only (150 spaces)
- Display employee parking pass
- Carpooling encouraged - priority parking for 3+ occupants

### Contact HR
- HR Office: Village Base, 2nd Floor
- Email: hr@alpinepeaks.com
- Emergency after-hours: Call Ski Patrol dispatch

*Full policies at employee.alpinepeaks.com*
', 'employee_handbook.md');

INSERT INTO SKI_RESORT_DB.DOCS.RESORT_DOCUMENTS (DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE)
VALUES ('HR-002', 'employee', 'Ski School Instructor Guidelines', '# Ski School Instructor Guidelines
## Teaching Excellence at Alpine Peaks

### Lesson Types & Ratios
We offer 5 lesson formats:

| Type | Max Students | Duration | Terrain |
|------|--------------|----------|---------|
| Beginner Group | 6 | 2 hours | Magic Carpet, Learning Area Lift area |
| Intermediate Group | 8 | 2 hours | Family Fun Quad, Sunshine Quad area |
| Advanced Group | 6 | 2 hours | Black Diamond Chair, Mid-Mountain Quad area |
| Private | 1-5 | 1-4 hours | Customized |
| Kids Camp | 4-6 | Full day | Age-appropriate |

### Instructor Certification Requirements
- PSIA/AASI Level 1: Can teach beginner group
- PSIA/AASI Level 2: Can teach intermediate, assist advanced
- PSIA/AASI Level 3: All lesson types, can mentor
- Children''s Specialist: Required for Kids Camp

### Lesson Flow (Group)
1. **Meet & Greet** (10 min): Equipment check, introductions, assess levels
2. **Safety Briefing** (5 min): Trail etiquette, stopping, falling
3. **Warm-up** (10 min): Flat terrain basics
4. **Skill Building** (60 min): Progressive terrain, drills
5. **Free Skiing** (25 min): Apply skills, fun focus
6. **Wrap-up** (10 min): Tips, next steps, photo op

### Teaching Zones by Level
**Beginners**:
- Primary: Summit Run, Eagle Ridge
- Lifts: Magic Carpet, Learning Area Lift

**Intermediate**:
- Primary: Powder Bowl, Family Way, Black Diamond
- Lifts: Family Fun Quad, Sunshine Quad, Cruiser 6-Pack

**Advanced**:
- Primary: North Face, Glade Runner
- Lifts: Black Diamond Chair, Mid-Mountain Quad

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
', 'ski_school_guidelines.md');

INSERT INTO SKI_RESORT_DB.DOCS.RESORT_DOCUMENTS (DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE)
VALUES ('PROD-001', 'product', 'Trail Guide and Terrain Overview', '# Trail Guide & Terrain Overview
## Alpine Peaks Resort - Know Before You Go

### Mountain Statistics
- **Summit Elevation**: 11,500 ft
- **Base Elevation**: 8,500 ft
- **Vertical Drop**: 3,000 ft
- **Skiable Acres**: 2,200
- **Number of Trails**: 15
- **Number of Lifts**: 18

### Trail Breakdown
| Difficulty | Trails | % of Terrain |
|------------|--------|--------------|
| 🟢 Beginner | 3 | 20% |
| 🔵 Intermediate | 5 | 35% |
| ⚫ Advanced | 4 | 30% |
| ⚫⚫ Expert | 3 | 15% |

### Featured Trails

**Summit Run** 🟢
The classic beginner''s run. Wide, gentle slope from Learning Area Lift with consistent pitch. Perfect for first-timers finding their ski legs.

**Family Way** 🟢
Family favorite! Extra-wide cruiser from Family Fun Quad. Connects to beginner-friendly terrain park features.

**Cruiser** 🔵
The ultimate intermediate cruiser. Long, rolling terrain off Cruiser 6-Pack. Groomed nightly, consistently excellent conditions.

**North Face** ⚫
True black diamond experience. Steep, mogul-prone, ungroomed. Access via Black Diamond Chair. Not for the faint of heart!

**Snowflake** ⚫
Technical steeps with variable snow. Expert-only terrain off Expert Chutes Chair.

**Avalanche** ⚫⚫
Our most challenging inbounds terrain. Avalanche-controlled bowl access via Expert Chutes Chair. Requires expert skills.

### Terrain Parks
- **Main Park** (Terrain Park Express): Progressive features for all levels
- **Mini Park** (Family Fun Quad): Intro features for beginners
- **Pro Line**: Competition-level jumps and rails (seasonal)

### Recommended Progressions

**Beginner → Intermediate** (Days 1-5):
Summit Run → Eagle Ridge → Family Way → Powder Bowl

**Intermediate → Advanced** (Days 5-10):
Cruiser → Black Diamond → Mogul Madness → North Face

**Advanced → Expert**:
North Face → Glade Runner → Timberline → Avalanche

### Real-Time Conditions
Check alpinepeaks.com/conditions or the Alpine Peaks app for:
- Trail open/closed status
- Grooming report
- Lift wait times
- Snow conditions by zone

*The mountain is waiting - see you on the slopes!*
', 'trail_guide.md');

INSERT INTO SKI_RESORT_DB.DOCS.RESORT_DOCUMENTS (DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE)
VALUES ('FEEDBACK-001', 'feedback', 'December 2024 Guest Feedback Summary', '# Guest Feedback Summary - December 2024
## Voice of Customer Analysis

### Overall Satisfaction
- **NPS Score**: 58 (Target: 65)
- **Total Responses**: 2,847
- **Response Rate**: 12% of unique visitors

### Top Positive Themes

**1. Snow Conditions (892 mentions)**
> "Best early season conditions in years! Powder Bowl was perfectly groomed."
> "Fresh powder in Alpine Bowl - felt like January skiing in December!"

**2. Staff Friendliness (634 mentions)**
> "Lift operators at Family Fun Quad were so helpful with my kids."
> "Rental staff at Village Base made fitting quick and painless."

**3. Food Quality (412 mentions)**
> "Summit restaurant exceeded expectations - great views and food!"
> "New grab-and-go options at Mid-Mountain are a game changer."

### Top Negative Themes

**1. Lift Wait Times (723 mentions)** ⚠️ PRIORITY
> "Waited 25 minutes for Summit Express Gondola on Saturday. Unacceptable."
> "Mid-Mountain Quad lines were brutal from 10am-1pm."
> "Why can''t you open more lifts on busy days?"

**Average Reported Wait**: 18 min (vs. 12 min target)
**Peak Complaint Days**: Dec 21-23 (Saturday-Monday holiday week)

**2. Parking Issues (389 mentions)**
> "Main Lot full by 9am - had to park in overflow."
> "Shuttle from Overflow Lot took 20 minutes."

**3. Rental Availability (267 mentions)**
> "No size 10 boots available at 10am on Saturday."
> "Demo skis sold out - drove 2 hours and couldn''t rent performance gear."

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
1. **Immediate**: Add signage for alternate lifts when Summit Express Gondola exceeds 15 min wait
2. **Short-term**: Expand rental inventory for size 8-10 boots
3. **Medium-term**: Launch wait time feature in mobile app
4. **Long-term**: Mid-Mountain Quad capacity upgrade (see Strategic Plan)

### Verbatim Highlights

*"This resort has amazing terrain but the operational execution doesn''t match.
I pay $130/day and spend 30% of it in lift lines. Please invest in capacity!"*
— Pass Holder, Dec 22

*"Our family had the BEST ski vacation. Lessons were fantastic,
kids went from pizza to parallel in 3 days. Will definitely return!"*
— Vacation Family, Dec 28

*"Pro tip: ski North Face in the morning before it gets tracked out.
Afternoon crowds on Black Diamond Chair make it not worth it."*
— Expert Skier, Dec 15

*Report compiled by Guest Experience Team*
', 'dec_2024_feedback.md');

INSERT INTO SKI_RESORT_DB.DOCS.RESORT_DOCUMENTS (DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE)
VALUES ('MEMO-001', 'memo', 'Operations Memo - Week of Dec 16, 2024', '# Weekly Operations Memo
## Week of December 16-22, 2024

**From**: Mountain Operations Director
**To**: All Department Heads
**Date**: December 15, 2024

---

### Weather Outlook
- **Monday-Wednesday**: Clear, temps 18-28°F, light winds
- **Thursday**: Storm arriving, 4-8" expected overnight
- **Friday-Sunday**: Post-storm clearing, POWDER CONDITIONS

⚠️ **Prepare for surge**: Friday will be BUSY. Last year''s comparable day saw 4,200 visitors.

### Staffing Adjustments

| Department | Mon-Wed | Thu | Fri-Sun |
|------------|---------|-----|---------|
| Lift Ops | Standard | -10% (weather) | +40% |
| Rentals | Standard | Standard | +50% |
| F&B | Standard | -20% | +60% |
| Ski Patrol | Standard | +20% (avy work) | +30% |

**Key Call-Outs**:
- Backbowl Access Chair and Powder Bowl Chair delayed opening Thursday for avalanche control
- Extra ticket windows Friday 7:30 AM
- All hands on deck Saturday - cancel non-essential PTO

### Lift Status

| Lift | Status | Notes |
|------|--------|-------|
| Summit Express Gondola | ✅ | New haul rope installed - running smooth |
| Eagle Ridge 6-Pack | ✅ | Minor drive issue resolved |
| Expert Chutes Chair | ⚠️ | Delayed opening Thu for control work |
| Backcountry Gate Access | ⚠️ | Backcountry gate closed Thu-Fri AM |

### Operational Priorities

**1. Wait Time Management**
Summit Express Gondola wait times hit 28 min last Saturday. This is unacceptable.
- Deploy line management staff by 9 AM on weekends
- Radio updates every 30 minutes to Dispatch
- Actively redirect guests to Eagle Ridge 6-Pack and Cruiser 6-Pack

**2. Rental Pre-staging**
Size 8-10 boots ran out by 10 AM last weekend.
- Pre-stage 50 additional pairs in those sizes
- Online reservation guests get priority pickup

**3. Parking Flow**
Main Lot filled by 8:45 AM Saturday.
- Open Overflow Lot overflow by 8 AM
- Shuttle service every 10 minutes when overflow active

### Safety Notes

- ICE WARNING: North Face and Glade Runner icy in mornings until grooming
- Summit Peak winds forecast 30+ mph Thursday - prepare for upper mountain hold

### Holiday Week Preview (Dec 21-Jan 5)

This is our biggest revenue period. Every department at 100%.
- Expected daily visitors: 3,500-4,500
- Season pass scan estimate: 1,400/day
- F&B revenue target: $85K/day

**Let''s execute flawlessly.**

— Mountain Ops
', 'ops_memo_dec16.md');

INSERT INTO SKI_RESORT_DB.DOCS.RESORT_DOCUMENTS (DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE)
VALUES ('MARKETING-001', 'marketing', 'Powder Alert Campaign - December 2024', '# Marketing Campaign Brief
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
> Last night''s storm dropped 8.2 inches of fresh snow across the mountain.
>
> **Current Conditions**:
> - Summit Peak: Fresh Snow, 8" new
> - Alpine Bowl: Fresh Snow, 7" new
> - Base Depth: 42 inches
>
> **Best Powder Runs**:
> - Powder Bowl (untracked until 10 AM)
> - Glade Runner (experts only - amazing!)
> - Powder Bowl Chair access for Alpine Bowl stashes
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
', 'powder_alert_campaign.md');

INSERT INTO SKI_RESORT_DB.DOCS.RESORT_DOCUMENTS (DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE)
VALUES ('FAQ-001', 'faq', 'Frequently Asked Questions', '# Frequently Asked Questions
## Alpine Peaks Resort - Guest Services Reference

### Tickets & Passes

**Q: What are your lift ticket prices?**
A: Adult day tickets are $129, child (6-12) $79, senior (65+) $99. Half-day tickets (starting noon) are $89. Book online for best pricing.

**Q: What''s included in a season pass?**
A: Season passes include unlimited skiing/riding with no blackout dates, 10% F&B discount, 15% rental discount, priority ski school booking, and free parking in Main Lot.

**Q: What''s your refund policy for tickets?**
A: Unused tickets can be refunded up to 48 hours before. If the mountain closes completely before noon, you receive a full credit. Partial closures do not qualify for refunds.

**Q: Do you offer multi-day discounts?**
A: Yes! 3-day passes are $99/day effective, 5-day passes are $89/day effective. Best value is the season pass at $899 (break-even at 7 visits).

### Operations

**Q: What are your operating hours?**
A: Lifts operate 9 AM - 4 PM daily. Summit Express Gondola opens at 8:45 AM and runs until 4:15 PM for download. Holiday periods may have extended hours.

**Q: How many lifts do you have?**
A: We operate 18 lifts with total capacity of 19,500 riders per hour. Our flagship Summit Express Gondola has 2,500/hour capacity.

**Q: Which lifts are best for beginners?**
A: Start with Magic Carpet (Magic Carpet) and Learning Area Lift (Learning Area). When ready to progress, Family Fun Quad accesses gentle green terrain.

**Q: What causes lift closures?**
A: High winds (35+ mph for high-speed lifts, 50+ mph for fixed-grip), lightning within 10 miles, or mechanical issues. Check our app for real-time status.

### Weather & Conditions

**Q: What are your different mountain zones?**
A: We have four zones: Summit Peak, North Ridge, Alpine Bowl, Village Base. Summit Peak (11,500 ft) is coldest/windiest, Village Base (8,500 ft) is warmest and most protected.

**Q: What do the snow condition ratings mean?**
A: Fresh Snow = new powder, Groomed = machine-prepared corduroy, Packed Powder = firm base, Spring Conditions = softer afternoon snow, Variable = mixed conditions.

**Q: Do you make snow?**
A: Yes! We have snowmaking on 60% of terrain including all beginner areas. We typically begin snowmaking in early November when temps allow.

### Rentals & Lessons

**Q: Do I need reservations for rentals?**
A: Reservations aren''t required but are strongly recommended, especially weekends and holidays. Book online for 15% discount and guaranteed equipment.

**Q: What''s included in a lesson?**
A: Group lessons include 2 hours instruction, lift ticket for designated learning terrain, and equipment if needed. Private lessons can access any terrain.

**Q: Do you have equipment for young children?**
A: Yes! We rent equipment starting at age 3. Our Family Fun Quad area has a dedicated kids zone.

### Dining & Services

**Q: Where can I eat on the mountain?**
A: We have 10 dining locations: 4 sit-down restaurants, 4 quick-service, and 2 bars. Summit restaurant has the best views!

**Q: Is there WiFi available?**
A: Free WiFi is available in all lodge areas. Coverage does not extend to lifts or trails.

**Q: Do you have lockers?**
A: Day lockers are available at Village Base ($15/day). Season locker rentals available for pass holders ($250/season).

### Safety

**Q: What''s the Your Responsibility Code?**
A: It''s the skier/rider code of conduct. Key points: stay in control, yield to people ahead, don''t stop where you''re not visible, look uphill before merging.

**Q: What should I do if there''s an accident?**
A: If you witness an incident, stay at the scene, call Ski Patrol (dial 911 from any lift or use orange emergency phones), and don''t move an injured person.

**Q: Can I ski out-of-bounds?**
A: Backcountry Gate Access provides backcountry access, but you must have avalanche gear (beacon, probe, shovel) and a partner. The gate may be closed during high hazard.

### Contact

**Guest Services**: 1-800-SKI-ALPS
**Website**: alpinepeaks.com
**App**: Search "Alpine Peaks" on iOS/Android

*Can''t find your answer? Chat with us in the app or visit any Guest Services desk!*
', 'faq.md');

INSERT INTO SKI_RESORT_DB.DOCS.RESORT_DOCUMENTS (DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE)
VALUES ('INCIDENT-001', 'incident', 'Monthly Incident Summary - December 2024', '# Monthly Incident Summary
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
| Falls | 68 | 53.5% | North Face, Black Diamond |
| Collisions | 31 | 24.4% | Cruiser, Family Way |
| Equipment Failure | 12 | 9.4% | Various |
| Medical (non-ski) | 9 | 7.1% | Base Lodge |
| Lift-Related | 4 | 3.1% | Family Fun Quad, Summit Express Gondola |
| Lost Skier | 3 | 2.4% | North Ridge |

### Incidents by Severity
- **Minor** (self-transport or released on-scene): 98 (77.2%)
- **Moderate** (toboggan transport to first aid): 21 (16.5%)
- **Serious** (ambulance/hospital): 8 (6.3%)

### High-Profile Incidents

**December 8 - Collision on Cruiser**
- Two intermediate skiers collided at trail merge
- One transported with suspected ACL injury
- Root cause: Poor visibility from intersection angle
- **Action**: Added signage and slow zone marking

**December 15 - Fall on Avalanche**
- Expert skier fell in steep chute
- Shoulder injury, transported to hospital
- Contributing factor: Icy conditions after wind event
- **Action**: Enhanced morning grooming rotation

**December 22 - Lift Incident at Family Fun Quad**
- Child''s ski tip caught on loading ramp
- Lift stopped, child assisted, no injury
- Root cause: Improper tip positioning
- **Action**: Additional safety guidance signage at load

### Location Analysis

**Highest Incident Trails**:
1. North Face - 18 incidents (14.2%)
   - Steep pitch, moguls, attracts intermediates beyond ability
2. Cruiser - 14 incidents (11.0%)
   - High traffic, trail merge point
3. Black Diamond - 12 incidents (9.4%)
   - Variable conditions, sun/shade transitions

**Lowest Incident Trails**:
- Summit Run, Eagle Ridge - 2 incidents each
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

1. **Signage Enhancement**: Add "Slow Zone" signs at Cruiser merge
2. **Grooming Priority**: Morning pass on North Face to address ice
3. **Patrol Positioning**: Station at Black Diamond/6 intersection during peak hours
4. **Guest Education**: App push notification about fatigue after 2+ hours

### Patrol Response Metrics
- Average response time: 4.2 minutes (target: <5 min) ✅
- Toboggan transport time: 8.7 minutes average
- First aid treatment capacity: Never exceeded

*Report prepared by Ski Patrol Director*
*All incidents reported per industry standards (NSAA guidelines)*
', 'incident_summary_dec2024.md');

-- Create Cortex Search Service
CREATE OR REPLACE CORTEX SEARCH SERVICE SKI_RESORT_DB.DOCS.RESORT_DOCS_SEARCH
  ON CONTENT
  ATTRIBUTES DOC_TYPE, TITLE
  WAREHOUSE = COMPUTE_WH
  TARGET_LAG = '1 day'
  AS (
    SELECT DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE
    FROM SKI_RESORT_DB.DOCS.RESORT_DOCUMENTS
  );
