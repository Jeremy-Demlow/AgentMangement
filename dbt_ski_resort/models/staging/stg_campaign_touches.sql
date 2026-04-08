-- Staging model for customer campaign touches
with source as (
    select * from {{ source('raw', 'customer_campaign_touches') }}
),

staged as (
    select
        touch_id,
        customer_id,
        campaign_id,
        channel,
        touch_timestamp,
        was_delivered,
        was_opened,
        open_timestamp,
        was_clicked,
        click_timestamp,
        click_url,
        converted,
        conversion_timestamp,
        conversion_type,
        conversion_value,
        conversion_sale_id,
        unsubscribed,
        created_at
    from source
)

select * from staged
