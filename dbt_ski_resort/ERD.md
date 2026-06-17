# Ski Resort Analytics — Entity Relationship Diagram

A detailed ASCII representation of the Kimball dimensional model. Readable in any text editor, terminal, or markdown viewer without rendering dependencies.

## Join Map — All Relationships

Every line represents a foreign key join. Read as: FACT_TABLE.FK_COLUMN → DIM_TABLE.PK_COLUMN.

```
                                         ┌───────────────┐
                                         │   DIM_DATE    │
                                         │  PK: DATE_KEY │
                                         └───────┬───────┘
                                                 │
         ┌───────────────┬───────────────┬───────┼───────┬───────────────┬───────────────┐
         │               │               │       │       │               │               │
         │               │               │       │       │               │               │
         ▼               ▼               ▼       ▼       ▼               ▼               ▼
   ┌───────────┐   ┌───────────┐   ┌─────────┐ │ ┌─────────┐   ┌───────────┐   ┌───────────┐
   │FACT_TICKET│   │FACT_LIFT_ │   │FACT_PASS│ │ │FACT_    │   │FACT_FOOD_ │   │FACT_      │
   │_SALES     │   │SCANS      │   │_USAGE   │ │ │RENTALS  │   │BEVERAGE   │   │WEATHER    │
   └─────┬─────┘   └─────┬─────┘   └─────────┘ │ └────┬────┘   └─────┬─────┘   └───────────┘
         │               │                      │      │               │
         │               │                      │      │               │
         │               │               ┌──────┴──────┴───────────────┴──────┐
         │               │               │                                     │
         │               │               ▼                                     ▼
         │               │         ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐
         │               │         │FACT_      │   │FACT_      │   │FACT_      │   │FACT_LIFT_ │
         │               │         │STAFFING   │   │INCIDENTS  │   │LESSONS    │   │MAINTENANCE│
         │               │         └───────────┘   └───────────┘   └───────────┘   └─────┬─────┘
         │               │                                                               │
         │               │         ┌───────────┐   ┌───────────┐   ┌───────────┐         │
         │               │         │FACT_      │   │FACT_      │   │FACT_      │         │
         │               │         │FEEDBACK   │   │GROOMING   │   │PARKING    │         │
         │               │         └───────────┘   └───────────┘   └───────────┘         │
         │               │                                                               │
         │               │                                                               │
         ▼               ▼                                                               ▼
   ┌─────────────┐ ┌─────────────┐                                                ┌─────────────┐
   │DIM_CUSTOMER │ │  DIM_LIFT   │                                                │  DIM_LIFT   │
   │PK:          │ │PK: LIFT_KEY │                                                │(same table) │
   │CUSTOMER_KEY │ └─────────────┘                                                └─────────────┘
   └──────┬──────┘
          │
          │  (also joined by FACT_RENTALS, FACT_FOOD_BEVERAGE, FACT_PASS_USAGE)
          │
          │
          ▼
   ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
   │                              COMPLETE JOIN REFERENCE                                         │
   ├─────────────────────────────────────────────────────────────────────────────────────────────┤
   │                                                                                             │
   │  FACT_TICKET_SALES                                                                          │
   │    ├── purchase_date_key ──────────────── → DIM_DATE.date_key                               │
   │    ├── customer_key ───────────────────── → DIM_CUSTOMER.customer_key                       │
   │    ├── ticket_type_key ────────────────── → DIM_TICKET_TYPE.ticket_type_key                 │
   │    └── location_key ───────────────────── → DIM_LOCATION.location_key                       │
   │                                                                                             │
   │  FACT_LIFT_SCANS                                                                            │
   │    ├── date_key ───────────────────────── → DIM_DATE.date_key                               │
   │    ├── customer_key ───────────────────── → DIM_CUSTOMER.customer_key                       │
   │    └── lift_key ───────────────────────── → DIM_LIFT.lift_key                               │
   │                                                                                             │
   │  FACT_PASS_USAGE                                                                            │
   │    ├── date_key ───────────────────────── → DIM_DATE.date_key                               │
   │    └── customer_key ───────────────────── → DIM_CUSTOMER.customer_key                       │
   │                                                                                             │
   │  FACT_RENTALS                                                                               │
   │    ├── rental_date_key ────────────────── → DIM_DATE.date_key                               │
   │    ├── customer_key ───────────────────── → DIM_CUSTOMER.customer_key                       │
   │    ├── product_key ────────────────────── → DIM_PRODUCT.product_key                         │
   │    └── location_key ───────────────────── → DIM_LOCATION.location_key                       │
   │                                                                                             │
   │  FACT_FOOD_BEVERAGE                                                                         │
   │    ├── transaction_date_key ───────────── → DIM_DATE.date_key                               │
   │    ├── customer_key ───────────────────── → DIM_CUSTOMER.customer_key                       │
   │    ├── product_key ────────────────────── → DIM_PRODUCT.product_key                         │
   │    └── location_key ───────────────────── → DIM_LOCATION.location_key                       │
   │                                                                                             │
   │  FACT_WEATHER                                                                               │
   │    └── date_key ───────────────────────── → DIM_DATE.date_key                               │
   │                                                                                             │
   │  FACT_STAFFING                                                                              │
   │    ├── schedule_date_key ──────────────── → DIM_DATE.date_key                               │
   │    └── location_key ───────────────────── → DIM_LOCATION.location_key                       │
   │                                                                                             │
   │  FACT_INCIDENTS                                                                             │
   │    └── date_key ───────────────────────── → DIM_DATE.date_key                               │
   │                                                                                             │
   │  FACT_LESSONS                                                                               │
   │    └── lesson_date_key ────────────────── → DIM_DATE.date_key                               │
   │                                                                                             │
   │  FACT_FEEDBACK                                                                              │
   │    └── feedback_date_key ──────────────── → DIM_DATE.date_key                               │
   │                                                                                             │
   │  FACT_GROOMING                                                                              │
   │    └── date_key ───────────────────────── → DIM_DATE.date_key                               │
   │                                                                                             │
   │  FACT_LIFT_MAINTENANCE                                                                      │
   │    ├── date_key ───────────────────────── → DIM_DATE.date_key                               │
   │    └── lift_key ───────────────────────── → DIM_LIFT.lift_key                               │
   │                                                                                             │
   │  FACT_PARKING                                                                               │
   │    └── (no dimension joins — flat fact)                                                     │
   │                                                                                             │
   │  FACT_SEASON_PASS_SALES                                                                     │
   │    └── (joins staging models, not conformed dims — future improvement)                      │
   │                                                                                             │
   │  FACT_MARKETING                                                                             │
   │    └── date_key ───────────────────────── → DIM_DATE.date_key                               │
   │                                                                                             │
   └─────────────────────────────────────────────────────────────────────────────────────────────┘

   Total: 26 foreign key relationships across 15 fact tables → 6 dimensions
```

## Join Cardinality

```
   Dimension              │ # Facts That Join │ Join Type          │ SCD Pattern
  ─────────────────────── │ ───────────────── │ ────────────────── │ ─────────────────────────
   DIM_DATE               │        13         │ INNER (via int key)│ N/A (generated spine)
   DIM_CUSTOMER           │         5         │ LEFT (SCD2)        │ ON customer_id AND is_current=TRUE
   DIM_TICKET_TYPE        │         1         │ LEFT (SCD2)        │ ON ticket_type_id AND is_current=TRUE
   DIM_PRODUCT            │         2         │ LEFT (SCD2)        │ ON product_key (surrogate)
   DIM_LOCATION           │         4         │ LEFT (surrogate)   │ ON location_key (surrogate)
   DIM_LIFT               │         2         │ LEFT (surrogate)   │ ON lift_key (surrogate)
```

## Star Schema Visual (Classic Kimball Layout)

```
                              ┌─────────────┐
                              │  DIM_DATE   │
                              │ (conformed) │
                              └──────┬──────┘
                                     │
            ┌────────────────────────┼────────────────────────┐
            │                        │                        │
            │    ┌───────────────────┼───────────────────┐    │
            │    │                   │                   │    │
            │    │    ┌──────────────┼──────────────┐    │    │
            │    │    │              │              │    │    │
            ▼    ▼    ▼              ▼              ▼    ▼    ▼
┌─────┐  ┌─────────────────────────────────────────────────────────┐  ┌─────┐
│ DIM │  │                                                         │  │ DIM │
│CUST.│◄─┤   FACT_TICKET_SALES    FACT_LIFT_SCANS    FACT_RENTALS  │──►│PROD.│
│     │  │                                                         │  │     │
└─────┘  │   FACT_FOOD_BEVERAGE   FACT_PASS_USAGE    FACT_WEATHER  │  └─────┘
         │                                                         │
┌─────┐  │   FACT_STAFFING        FACT_INCIDENTS     FACT_LESSONS  │  ┌─────┐
│ DIM │  │                                                         │  │ DIM │
│TICK.│◄─┤   FACT_FEEDBACK        FACT_GROOMING      FACT_MAINT.   │──►│LIFT │
│TYPE │  │                                                         │  │     │
└─────┘  │   FACT_PARKING         FACT_MARKETING     FACT_PASSES   │  └─────┘
         │                                                         │
         └──────────────────────────────┬──────────────────────────┘
                                        │
                                        ▼
                                  ┌───────────┐
                                  │    DIM    │
                                  │ LOCATION  │
                                  └───────────┘


   CONFORMED DIMENSIONS (shared across multiple facts):
   ════════════════════════════════════════════════════
   DIM_DATE ────────── joins 13 of 15 facts (universal time dimension)
   DIM_CUSTOMER ────── joins 5 facts (visitor-attributed transactions)
   DIM_LOCATION ────── joins 4 facts (venue-attributed events)
   DIM_LIFT ────────── joins 2 facts (lift-specific operations)
   DIM_PRODUCT ─────── joins 2 facts (item-level spend)
   DIM_TICKET_TYPE ─── joins 1 fact  (ticket sales only)
```

## Star Schema Overview

```
                                    ┌─────────────────────────────────────┐
                                    │            DIM_DATE                  │
                                    │─────────────────────────────────────│
                                    │ DATE_KEY (PK)        INT YYYYMMDD   │
                                    │ FULL_DATE            DATE            │
                                    │ DAY_NAME             VARCHAR(3)      │
                                    │ DAY_OF_WEEK          NUMBER(2)       │
                                    │ WEEK_OF_YEAR         NUMBER(2)       │
                                    │ MONTH_NUM            NUMBER(2)       │
                                    │ MONTH_NAME           VARCHAR(3)      │
                                    │ QUARTER_NUM          NUMBER(2)       │
                                    │ CALENDAR_YEAR        NUMBER(4)       │
                                    │ SKI_SEASON           VARCHAR         │
                                    │ IS_IN_SEASON         BOOLEAN         │
                                    │ SEASON_TYPE          VARCHAR(6)      │
                                    │   ↳ 'winter' (Nov-Apr)              │
                                    │   ↳ 'summer' (May-Oct)              │
                                    │ IS_SUMMER_SEASON     BOOLEAN         │
                                    │ IS_WEEKEND           BOOLEAN         │
                                    │ IS_HOLIDAY           BOOLEAN         │
                                    │ HOLIDAY_NAME         VARCHAR         │
                                    │ SNOW_CONDITION       VARCHAR(9)      │
                                    │ IS_OPERATING         BOOLEAN         │
                                    └──────────────────┬──────────────────┘
                                                       │
              ┌────────────────────┬───────────────────┼───────────────────┬────────────────────┐
              │                    │                   │                   │                    │
              ▼                    ▼                   ▼                   ▼                    ▼
┌──────────────────────┐ ┌─────────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  FACT_TICKET_SALES   │ │   FACT_LIFT_SCANS   │ │  FACT_PASS_USAGE │ │   FACT_RENTALS   │ │ FACT_FOOD_BEVER. │
│──────────────────────│ │─────────────────────│ │──────────────────│ │──────────────────│ │──────────────────│
│ SALE_KEY (PK)        │ │ SCAN_KEY (PK)       │ │ USAGE_KEY (PK)   │ │ RENTAL_KEY (PK)  │ │ TRANSACTION_KEY  │
│ PURCHASE_DATE_KEY►DT │ │ DATE_KEY►DT         │ │ DATE_KEY►DT      │ │ RENTAL_DATE_KEY► │ │ TXN_DATE_KEY►DT  │
│ CUSTOMER_KEY►CU      │ │ CUSTOMER_KEY►CU     │ │ CUSTOMER_KEY►CU  │ │ CUSTOMER_KEY►CU  │ │ CUSTOMER_KEY►CU  │
│ TICKET_TYPE_KEY►TT   │ │ LIFT_KEY►LF         │ │ VISIT_DATE       │ │ PRODUCT_KEY►PR   │ │ PRODUCT_KEY►PR   │
│ LOCATION_KEY►LO      │ │ SCAN_TIMESTAMP      │ │ TOTAL_SCANS      │ │ LOCATION_KEY►LO  │ │ LOCATION_KEY►LO  │
│ PURCHASE_AMOUNT      │ │ WAIT_TIME_MINUTES   │ │ FIRST_SCAN_TIME  │ │ RENTAL_AMOUNT    │ │ TOTAL_AMOUNT     │
│ TICKET_CATEGORY      │ │ SCAN_HOUR           │ │ LAST_SCAN_TIME   │ │ RENTAL_DURATION  │ │ ITEM_COUNT       │
│ PURCHASE_CHANNEL     │ │ RUNS_COUNT          │ │ UNIQUE_LIFTS     │ │ PRODUCT_ID       │ │ UPSELL_AMOUNT    │
│ IS_ADVANCE_PURCHASE  │ │                     │ │                  │ │                  │ │                  │
└──────────────────────┘ └─────────────────────┘ └──────────────────┘ └──────────────────┘ └──────────────────┘
         │ │                      │                                            │                    │
         │ │                      │                                            │                    │
         │ ▼                      ▼                                            ▼                    ▼
         │ ┌─────────────────────────────────────┐               ┌─────────────────────────────────────┐
         │ │          DIM_CUSTOMER (SCD2)         │               │          DIM_PRODUCT (SCD2)         │
         │ │─────────────────────────────────────│               │─────────────────────────────────────│
         │ │ CUSTOMER_KEY (PK)     SURROGATE     │               │ PRODUCT_KEY (PK)      SURROGATE     │
         │ │ CUSTOMER_ID           NATURAL KEY   │               │ PRODUCT_ID            NATURAL KEY   │
         │ │ FIRST_NAME            VARCHAR        │               │ PRODUCT_NAME          VARCHAR        │
         │ │ LAST_NAME             VARCHAR        │               │ PRODUCT_CATEGORY      VARCHAR        │
         │ │ EMAIL                 VARCHAR        │               │   ↳ rental, food, beverage          │
         │ │ CUSTOMER_SEGMENT      VARCHAR        │               │ PRODUCT_TYPE          VARCHAR        │
         │ │   ↳ Local Pass Holder               │               │   ↳ ski, snowboard, bike, safety    │
         │ │   ↳ Weekend Warrior                 │               │   ↳ meal, snack, hot, cold, alcohol │
         │ │   ↳ Vacation Family                 │               │ PRICE                 NUMBER         │
         │ │   ↳ Day Tripper                     │               │ VALID_FROM            TIMESTAMP      │
         │ │   ↳ Expert/Backcountry              │               │ VALID_TO              TIMESTAMP      │
         │ │   ↳ Group/Corporate                 │               │ IS_CURRENT            BOOLEAN        │
         │ │   ↳ Beginner/First-Timer            │               └─────────────────────────────────────┘
         │ │ AGE_GROUP             VARCHAR        │
         │ │ HOME_STATE            VARCHAR        │
         │ │ IS_PASS_HOLDER        BOOLEAN        │
         │ │ VALID_FROM            TIMESTAMP      │
         │ │ VALID_TO              TIMESTAMP      │
         │ │ IS_CURRENT            BOOLEAN        │
         │ └─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐               ┌─────────────────────────────────────┐
│      DIM_TICKET_TYPE (SCD2)         │               │            DIM_LOCATION             │
│─────────────────────────────────────│               │─────────────────────────────────────│
│ TICKET_TYPE_KEY (PK)  SURROGATE     │               │ LOCATION_KEY (PK)    SURROGATE      │
│ TICKET_TYPE_ID        NATURAL KEY   │               │ LOCATION_ID          NATURAL KEY    │
│ TICKET_NAME           VARCHAR        │               │ LOCATION_NAME        VARCHAR         │
│ TICKET_CATEGORY       VARCHAR        │               │ LOCATION_TYPE        VARCHAR         │
│   ↳ day_pass  (TKT001-003,015-016) │               │   ↳ rental_shop, restaurant         │
│   ↳ half_day  (TKT004, TKT017)     │               │   ↳ ticket_window, lodge             │
│   ↳ multi_day (TKT005-007)         │               │ MOUNTAIN_ZONE        VARCHAR         │
│   ↳ season_pass (TKT008-014,018)   │               │   ↳ Base, Mid-Mountain               │
│   ↳ summer_activity (TKT_BIKE,     │               │   ↳ Summit, Back Bowl                │
│      TKT_HIKE, TKT_GONDOLA,        │               │ ELEVATION            NUMBER          │
│      TKT_CONCERT, TKT_COMBO)       │               └─────────────────────────────────────┘
│ DURATION_DAYS         NUMBER         │
│ ACCESS_LEVEL          VARCHAR        │
│ PRICE                 NUMBER         │
│ VALID_FROM            TIMESTAMP      │
│ VALID_TO              TIMESTAMP      │
│ IS_CURRENT            BOOLEAN        │
└─────────────────────────────────────┘


┌─────────────────────────────────────┐
│             DIM_LIFT                 │
│─────────────────────────────────────│
│ LIFT_KEY (PK)        SURROGATE      │
│ LIFT_ID              NATURAL KEY    │
│ LIFT_NAME            VARCHAR         │
│ LIFT_TYPE            VARCHAR         │
│   ↳ Gondola (2 lifts)              │
│   ↳ Chairlift (16 lifts)           │
│ TERRAIN_TYPE         VARCHAR         │
│   ↳ Beginner, Intermediate         │
│   ↳ Advanced, Expert               │
│ VERTICAL_RISE        NUMBER          │
│ CAPACITY_PER_HOUR    NUMBER          │
│ MOUNTAIN_ZONE        VARCHAR         │
│ SUMMER_OPERATING     BOOLEAN         │
│   ↳ TRUE for L001,L002,L004,       │
│     L009,L010 (5 summer lifts)      │
└─────────────┬───────────────────────┘
              │
              ▼
```

## Secondary Fact Tables (Operational)

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    DIM_DATE (FK: DATE_KEY)                                          │
└────────┬──────────┬──────────┬───────────┬───────────┬───────────┬──────────┬──────────────────────┘
         │          │          │           │           │           │          │
         ▼          ▼          ▼           ▼           ▼           ▼          ▼
┌────────────────┐┌────────────────┐┌────────────────┐┌────────────────┐┌────────────────┐┌────────────────┐┌────────────────┐
│ FACT_WEATHER   ││ FACT_STAFFING  ││ FACT_INCIDENTS ││ FACT_LESSONS   ││ FACT_FEEDBACK  ││ FACT_GROOMING  ││FACT_LIFT_MAINT.│
│────────────────││────────────────││────────────────││────────────────││────────────────││────────────────││────────────────│
│weather_key (PK)││staffing_key PK ││incident_id (PK)││lesson_id (PK)  ││feedback_id (PK)││grooming_key PK ││maintenance_key │
│date_key►DT     ││sched_date_key► ││date_key►DT     ││lesson_date_key►││feedback_date_k►││date_key►DT     ││date_key►DT     │
│mountain_zone   ││department      ││incident_date   ││lesson_date     ││feedback_date   ││trail_name      ││lift_key►LF     │
│weather_date    ││job_role        ││incident_type   ││sport_type      ││category        ││grooming_type   ││maintenance_type│
│snowfall_inches ││scheduled_staff ││  ↳ collision   ││  ↳ ski         ││  ↳ lift_ops    ││condition_before││maintenance_cat │
│base_depth      ││actual_staff    ││  ↳ fall        ││  ↳ snowboard   ││  ↳ ski_school  ││condition_after ││downtime_minutes│
│temp_high_f     ││coverage_pct    ││  ↳ lost_skier  ││  ↳ mountain_   ││  ↳ rental_shop ││duration_minutes││repair_cost     │
│temp_low_f      ││overtime_hours  ││  ↳ bike_crash  ││    bike        ││  ↳ food_service││fuel_gallons    ││inspector_id    │
│wind_speed_mph  ││location_key►LO ││  ↳ trail_fall  ││  ↳ hiking      ││  ↳ bike_park   ││snow_depth      ││notes           │
│visibility      ││                ││  ↳ dehydration ││  ↳ adventure   ││  ↳ trail_cond  ││                ││                │
│snow_condition  ││                ││  ↳ wildlife    ││lesson_type     ││sentiment       ││                ││                │
│is_powder_day   ││                ││severity        ││skill_level     ││nps_score       ││                ││                │
│                ││                ││severity_score  ││instructor_name ││rating          ││                ││                │
│                ││                ││patrol_response ││group_size      ││likelihood_to_  ││                ││                │
│                ││                ││transport_req   ││total_lesson_rev││  return        ││                ││                │
│                ││                ││trail_name      ││student_rating  ││resolved        ││                ││                │
│                ││                ││                ││booking_channel ││response_time_  ││                ││                │
│                ││                ││                ││completed       ││  days          ││                ││                │
└────────────────┘└────────────────┘└────────────────┘└────────────────┘└────────────────┘└────────────────┘└────────────────┘
```

## Relationship Legend

```
Symbol    Meaning
──────    ──────────────────────────────────────────
►DT       Foreign key to DIM_DATE.DATE_KEY
►CU       Foreign key to DIM_CUSTOMER.CUSTOMER_KEY
►TT       Foreign key to DIM_TICKET_TYPE.TICKET_TYPE_KEY
►PR       Foreign key to DIM_PRODUCT.PRODUCT_KEY
►LO       Foreign key to DIM_LOCATION.LOCATION_KEY
►LF       Foreign key to DIM_LIFT.LIFT_KEY
(PK)      Primary key
(SCD2)    Slowly Changing Dimension Type 2
```

## Semantic View Coverage Map

Shows which fact and dimension tables each semantic view queries:

```
                           DIM_    DIM_     DIM_      DIM_     DIM_     DIM_
Semantic View              DATE  CUSTOMER  TICKET   PRODUCT  LOCATION   LIFT
─────────────────────────  ────  ────────  ──────   ───────  ────────  ─────
sem_daily_summary           ●       ●                                    ●
sem_revenue                 ●       ●        ●        ●        ●
sem_operations              ●                                   ●        ●
sem_lessons_analytics       ●
sem_safety_incidents        ●
sem_customer_satisfaction   ●
sem_staffing_analytics      ●                                   ●
sem_weather_analytics       ●
sem_passholder_analytics    ●       ●
sem_marketing_analytics     ●
sem_customer_behavior       ●       ●

                           FACT_    FACT_    FACT_    FACT_    FACT_    FACT_    FACT_    FACT_    FACT_    FACT_    FACT_
Semantic View              TICKET   LIFT_    PASS_    RENT-    F&B      WEATH    STAFF    INCID    LESS-    FEED-    GROOM
                           SALES    SCANS    USAGE    ALS                ER      ING      ENTS     ONS      BACK     ING
─────────────────────────  ──────   ─────    ─────    ─────    ────    ─────    ─────    ─────    ─────    ─────    ─────
sem_daily_summary           ●        ●        ●        ●       ●
sem_revenue                 ●                           ●       ●
sem_operations                       ●                                                                              ●
sem_lessons_analytics                                                                             ●
sem_safety_incidents                                                                     ●
sem_customer_satisfaction                                                                                   ●
sem_staffing_analytics                                                           ●
sem_weather_analytics                                                    ●
sem_passholder_analytics                      ●
sem_marketing_analytics
sem_customer_behavior                         ●
```

## Incremental Strategy Summary

```
┌───────────────────────┬──────────────────────┬─────────────────────┬──────────────────┐
│ Fact Table            │ Unique Key           │ Incremental Column  │ cluster_by       │
├───────────────────────┼──────────────────────┼─────────────────────┼──────────────────┤
│ fact_ticket_sales     │ sale_key             │ purchase_timestamp  │ purchase_date_key│
│ fact_lift_scans       │ scan_key             │ scan_timestamp      │ date_key         │
│ fact_pass_usage       │ usage_key            │ visit_date          │ date_key         │
│ fact_rentals          │ rental_key           │ rental_timestamp    │ rental_date_key  │
│ fact_food_beverage    │ transaction_key      │ transaction_timest. │ txn_date_key     │
│ fact_weather          │ weather_key          │ created_at          │ -                │
│ fact_staffing         │ staffing_key         │ created_at          │ -                │
│ fact_incidents        │ incident_id          │ created_at          │ -                │
│ fact_lessons          │ lesson_id            │ created_at          │ lesson_date_key  │
│ fact_feedback         │ feedback_id          │ created_at          │ feedback_date_key│
│ fact_grooming         │ grooming_key         │ created_at          │ -                │
│ fact_lift_maintenance │ maintenance_key      │ created_at          │ -                │
│ fact_parking          │ record_id            │ created_at          │ -                │
│ fact_season_pass_sales│ sale_id              │ created_at          │ -                │
│ fact_marketing        │ marketing_key        │ created_at          │ -                │
└───────────────────────┴──────────────────────┴─────────────────────┴──────────────────┘

Strategy: MERGE (default for all). Full-refresh required when adding columns.
```

## Seasonal Data Reference

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              WINTER (November - April)                                    │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ Ticket Types:  TKT001-TKT018 (day_pass, half_day, multi_day, season_pass)               │
│ Activities:    Skiing, snowboarding, night skiing                                        │
│ Lifts:         All 18 (2 gondolas + 16 chairlifts)                                       │
│ Lessons:       beginner_group, intermediate_group, advanced_group, private, kids_camp     │
│ Incidents:     collision, fall, lost_skier, frostbite, equipment_failure                  │
│ Grooming:      full_groom, touch_up, mogul_maintenance, park_build                       │
│ Multiplier:    0.5 (Nov) → 1.5 (Jan) → 0.7 (Apr)                                       │
│ Holidays:      Christmas (2.5x), New Year (2.5x), Presidents' Week (1.8x), MLK (1.5x)  │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              SUMMER (May - October)                                       │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ Ticket Types:  TKT_BIKE ($69), TKT_HIKE ($25), TKT_GONDOLA ($39),                       │
│                TKT_CONCERT ($55), TKT_COMBO ($89)                                        │
│ Activities:    Bike park, hiking, scenic gondola, concerts, zip lines, climbing wall      │
│ Lifts:         5 of 18 (L001, L002, L004, L009, L010) — bike uplift + scenic            │
│ Lessons:       mountain_bike_beginner/intermediate/advanced, guided_hike,                 │
│                kids_adventure_camp                                                        │
│ Incidents:     bike_crash, trail_fall, dehydration, wildlife_encounter,                   │
│                equipment_failure, medical                                                 │
│ Grooming:      trail_repair, brush_clearing, drainage_work                               │
│ Rentals:       Mountain Bike ($65), E-Bike ($95), Hiking Poles ($15),                    │
│                Climbing Gear ($45), Bike Helmet ($20), Bike Armor ($30)                   │
│ Multiplier:    0.3 (May/Oct) → 0.8 (Jul/Aug)                                            │
│ Holidays:      Memorial Day (1.8x), July 4th (2.5x), Labor Day (1.8x)                   │
│ Staffing:      Smaller crews — Lift Ops, Rentals, F&B, Tickets, Trail Patrol, Grounds    │
└─────────────────────────────────────────────────────────────────────────────────────────┘

Filtering:  WHERE DIM_DATE.SEASON_TYPE = 'winter'  or  'summer'
            WHERE DIM_DATE.IS_SUMMER_SEASON = TRUE
```
