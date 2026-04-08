-- Staging model for marketing campaigns
select * from {{ source('raw', 'marketing_campaigns') }}
