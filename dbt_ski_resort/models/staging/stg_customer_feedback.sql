{{
    config(
        materialized='view',
        schema='staging'
    )
}}

-- Staging model for customer feedback
-- Type-safe with derived fields for analysis

with source as (
    select * from {{ source('raw', 'customer_feedback') }}
),

staged as (
    select
        -- Keys
        feedback_id,
        customer_id,
        survey_id,

        -- Dates
        feedback_date::date as feedback_date,
        visit_date::date as visit_date,
        response_date::date as response_date,
        resolution_date::date as resolution_date,

        -- Feedback details
        feedback_type,
        category,
        subcategory,
        source,

        -- Scores (ensure numeric)
        nps_score::int as nps_score,
        satisfaction_score::float as satisfaction_score,
        likelihood_to_return::int as likelihood_to_return,
        likelihood_to_recommend::int as likelihood_to_recommend,
        sentiment_score::float as sentiment_score,

        -- Sentiment classification
        LOWER(sentiment) AS sentiment,
        case
            when nps_score >= 9 then 'Promoter'
            when nps_score >= 7 then 'Passive'
            else 'Detractor'
        end as nps_category,

        -- Text fields
        feedback_text,
        response_text,
        responded_by,

        -- Status flags
        resolved::boolean as resolved,
        escalated::boolean as escalated,

        -- Audit
        created_at

    from source
    where feedback_id is not null
    qualify row_number() over (partition by feedback_id order by created_at desc) = 1
)

select * from staged
