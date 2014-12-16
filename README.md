py-postmates
============

Python client for Postmates API

Example Usage:

```python
import postmates as pm

api = pm.PostmatesAPI(<YOUR_API_KEY>, <YOUR_CUSTOMER_ID>)

# get a quote for your delivery

pickup = pm.Location('Alice', '100 Start St, San Francisco, CA', '415-555-0000')
dropoff = pm.Location('Bob', '200 End St, San Francisco, CA', '415-777-9999')

quote = pm.DeliveryQuote(pickup.address, dropoff.address)

# create a delivery and schedule it

delivery = Delivery(api, 'a manifest', pickup, dropoff)
delivery.create()

# update the status of a pending delivery
delivery.update_status()

# if nothing's happened yet, you can cancel (but it will still cost you)
delivery.cancel()
```

Have fun!
