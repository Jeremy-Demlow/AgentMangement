{{
    config(
        materialized='incremental',
        unique_key='sale_id',
        on_schema_change='sync_all_columns'
    )
}}

with season_pass_sales as (
    select * from {{ ref('stg_season_pass_sales') }}
),

customers as (
    select customer_id, customer_segment from {{ ref('stg_customers') }}
),

campaigns as (
    select campaign_id, campaign_name, campaign_type
    from {{ ref('stg_marketing_campaigns') }}
),

final as (
    select
        sps.sale_id,
        sps.customer_id,
        c.customer_segment,
        sps.ticket_type_id,
        sps.purchase_date,
        sps.valid_season,
        sps.purchase_amount,
        sps.original_price,
        sps.discount_amount,
        sps.payment_method,
        sps.purchase_channel,
        sps.is_renewal,
        sps.previous_pass_type,
        sps.promo_code,
        sps.campaign_id,
        camp.campaign_name,
        camp.campaign_type,
        sps.payment_plan,
        sps.payment_plan_months,
        -- Calculated metrics
        case when sps.original_price > 0
            then round((sps.original_price - sps.purchase_amount) / sps.original_price * 100, 2)
            else 0 end as discount_percent,
        case when sps.is_renewal then 'Renewal' else 'New' end as customer_type,
        sps.created_at
    from season_pass_sales sps
    left join customers c on sps.customer_id = c.customer_id
    left join campaigns camp on sps.campaign_id = camp.campaign_id
)

select * from final
{% if is_incremental() %}
where created_at > (select max(created_at) from {{ this }})
{% endif %}
