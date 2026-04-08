{{
    config(
        materialized='incremental',
        unique_key='feedback_id',
        on_schema_change='sync_all_columns'
    )
}}

with feedback as (
    select * from {{ ref('stg_customer_feedback') }}
),

customers as (
    select customer_id, customer_segment from {{ ref('stg_customers') }}
),

final as (
    select
        f.feedback_id,
        f.customer_id,
        c.customer_segment,
        f.feedback_date,
        f.visit_date,
        f.feedback_type,
        f.category,
        f.subcategory,
        f.satisfaction_score as rating,
        f.sentiment,
        f.sentiment_score,
        f.feedback_text,
        f.response_text,
        f.response_date,
        f.responded_by,
        f.resolved,
        f.resolution_date,
        f.nps_score,
        f.likelihood_to_recommend,
        f.likelihood_to_return,
        f.source,
        -- Response time in days
        case when f.response_date is not null and f.feedback_date is not null
            then datediff('day', f.feedback_date, f.response_date)
            else null
        end as response_time_days,
        f.created_at
    from feedback f
    left join customers c on f.customer_id = c.customer_id
)

select * from final
{% if is_incremental() %}
where created_at > (select max(created_at) from {{ this }})
{% endif %}
