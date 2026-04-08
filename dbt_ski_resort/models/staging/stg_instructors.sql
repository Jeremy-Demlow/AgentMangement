-- Staging model for ski instructors
select * from {{ source('raw', 'instructors') }}
