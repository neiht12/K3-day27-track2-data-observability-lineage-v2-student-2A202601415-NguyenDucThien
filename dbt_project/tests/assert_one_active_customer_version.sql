-- A customer with multiple active SCD rows would multiply joined order rows.
select
    customer_id,
    count(*) as active_versions
from {{ ref('stg_customers') }}
where is_active = true
group by customer_id
having count(*) > 1
