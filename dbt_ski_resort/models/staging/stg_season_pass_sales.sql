-- Staging model for season pass sales
with source as (
    select * from {{ source('raw', 'season_pass_sales') }}
),

staged as (
    select
        sale_id,
        customer_id,
        ticket_type_id,
        purchase_date,
        valid_season,
        purchase_amount,
        original_price,
        discount_amount,
        payment_method,
        purchase_channel,
        is_renewal,
        previous_pass_type,
        promo_code,
        campaign_id,
        payment_plan,
        payment_plan_months,
        created_at
    from source
)

select * from staged
