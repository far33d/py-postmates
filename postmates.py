
import requests
from datetime import datetime
from dateutil import tz

__all__ = ['PostmatesAPI', 'PostmatesAPIException',
           'DeliveryQuote', 'Delivery', 'Location']

class PostmatesAPI(object):

  BASE_URL = 'https://api.postmates.com'

  def __init__(self, api_key, customer_id=None, version='v1'):
    self.api_key = api_key
    self.customer_id = customer_id
    self.version = version

  def post_delivery_quote(self, pickup_address, dropoff_address):
    url = self._delivery_quote_url()

    params = {
      'pickup_address': pickup_address,
      'dropoff_address': dropoff_address,
    }

    return self._make_request(url, data=params, type='post')

  def post_delivery_request(self, delivery):
    url = self._delivery_url()
    params = delivery.post_data()
    return self._make_request(url, data=params, type='post')

  def get_delivery_data(self, id):
    url = self._delivery_url(delivery_id=id)
    return self._make_request(url, type='get')

  def post_cancel_delivery(self, id):
    url = self._delivery_url(delivery_id=id, cancel=True)
    return self._make_request(url, type='post')

  def get_all_deliveries(self, ongoing=True):
    url = self._delivery_url()

    params = {}
    # this is busted?
    #if ongoing:
    #  params['filter'] = 'ongoing'

    return self._make_request(url, data=params, type='get')

  def _base_url(self):
    return '%s/%s/customers/%s' % (self.BASE_URL, self.version, self.customer_id)

  def _delivery_quote_url(self):
    return '%s/delivery_quotes' % self._base_url()

  def _delivery_url(self, delivery_id=None, cancel=False):
    url = '%s/deliveries' % self._base_url()

    if delivery_id:
      url = '%s/%s' % (url, delivery_id)

    if cancel:
      url = '%s/cancel' % url

    return url

  def _make_request(self, url, data=None, type='get'):
    if type == 'post':
      response = requests.post(url, data=data, auth=(self.api_key, ''))
    elif type == 'get':
      response = requests.get(url, params=data, auth=(self.api_key, ''))
    else:
      raise PostmatesAPIException('only gets and posts, yo')

    if not response.ok:
      raise PostmatesAPIException(response.json())

    return response.json()

class DeliveryQuote(object):

  def __init__(self, api, pickup_address, dropoff_address):

    data = api.post_delivery_quote(pickup_address, dropoff_address)

    self.pickup_address = pickup_address
    self.dropoff_address = dropoff_address

    self.quote_id = data['id']
    self.created = _parse_date(data['created'])
    self.currency = data['currency']
    self.dropoff_eta = _parse_date(data['dropoff_eta'])
    self.duration = data['duration']
    self.expires = _parse_date(data['expires'])
    self.fee = data['fee']

  @property
  def expired(self):
    now = datetime.now().replace(tzinfo=tz.tzutc())
    return self.expires < now

  def __repr__(self):
    s = []
    s.append('Postmates Delivery Quote --------')
    s.append('ID: %s' % self.quote_id)
    s.append('Created At: %s' % _to_local_tz(self.created))
    s.append('Fee: $%.2f %s' % (self.fee/100.0, self.currency))
    s.append('Dropoff ETA: %s' % _to_local_tz(self.dropoff_eta))
    s.append('Expires: %s' % _to_local_tz(self.expires))
    s.append('Expired: %s' % self.expired)

    return '\n'.join(s)

class Delivery(object):

  STATUS_UNSUBMITTED = 'unsubmitted'
  STATUS_PENDING = 'pending'
  STATUS_PICKUP = 'pickup'
  STATUS_DROPOFF = 'dropoff'
  STATUS_CANCELED = 'canceled'
  STATUS_DELIVERED = 'delivered'

  def __init__(self, api, manifest, pickup, dropoff, quote=None):

    self.api = api
    self.manifest = manifest
    self.pickup = pickup
    self.dropoff = dropoff
    self.quote = quote

    self.delivery_id = None
    self.status = Delivery.STATUS_UNSUBMITTED
    self.complete = False
    self.pickup_eta = None
    self.dropoff_eta = None
    self.dropoff_deadline = None
    self.fee = None
    self.currency = None
    self.courier = None

  def create(self):
    if not self.pickup._is_valid():
      raise PostmatesAPIException('Pickup is missing required attributes\n %s' % pickup)

    if not self.dropoff._is_valid():
      raise PostmatesAPIException('Dropoff is missing required attributes\n %s' % dropoff)

    if self.status != Delivery.STATUS_UNSUBMITTED:
      raise PostmatesAPIException('Cannot create a delivery that has already been submitted')

    if self.quote and self.quote.expired:
      raise PostmatesAPIException('Attempting to submit expired delivery quote')

    delivery_data = self.api.post_delivery_request(self)
    self._update_from_request(delivery_data)

  def update_status(self):
    if self.delivery_id is None:
      return

    delivery_data = self.api.get_delivery_data(self.delivery_id)
    self._update_from_request(delivery_data)

  def cancel(self):
    if self.status not in (Delivery.STATUS_PENDING, Delivery.STATUS_PICKUP):
      raise PostmatesAPIException('Can only cancel deliveries not yet picked up')

    delivery_data = self.api.post_cancel_delivery(self.delivery_id)
    self._update_from_request(delivery_data)

  def _update_from_request(self, data):
    self.delivery_id = data['id']
    self.status = data['status']
    self.complete = data['complete']
    self.pickup_eta = _parse_date(data['pickup_eta'])
    self.dropoff_eta = _parse_date(data['dropoff_eta'])
    self.dropoff_deadline = _parse_date(data['dropoff_deadline'])
    self.fee = data['fee']
    self.currency = data['currency']
    self.courier = data['courier']

  def post_data(self):

    post_data = {}

    post_data['manifest'] = self.manifest
    post_data.update(self.pickup.post_data('pickup'))
    post_data.update(self.dropoff.post_data('dropoff'))

    if self.quote:
      post_data['quote_id'] = self.quote.quote_id

    return post_data

  def __repr__(self):
    s = []
    s.append('Postmates Delivery')
    s.append('Manifest (required): %s' % self.manifest)
    s.append('Pickup --------------')
    s.append(str(self.pickup))
    s.append('Dropoff --------------')
    s.append(str(self.dropoff))

    if self.status != Delivery.STATUS_UNSUBMITTED:
      s.append('Status --------------')
      s.append('Delivery ID: %s' % self.delivery_id)
      s.append('Status: %s' % self.status)
      s.append('Complete: %s' % self.complete)
      s.append('Pickup ETA: %s' % _to_local_tz(self.pickup_eta))
      s.append('Dropoff ETA: %s' % _to_local_tz(self.dropoff_eta))
      s.append('Dropoff Deadline: %s' % _to_local_tz(self.dropoff_deadline))
      s.append('Fee: $%.2f %s' % (self.fee / 100.0, self.currency))
      s.append('Courier: %s' % self.courier)

    return '\n'.join(s)

class Location(object):

  def __init__(self, name, address, phone_number, business_name=None, notes=None):
    self.name = name
    self.address = address
    self.phone_number = phone_number
    self.business_name = business_name
    self.notes = notes

  def _is_valid(self):
    if self.name is None or self.address is None or self.phone_number is None:
      return False
    return True

  def __repr__(self):
    s = []
    s.append('Name (required): %s' % self.name)
    s.append('Address (required): %s' % self.address)
    s.append('Phone Number (required): %s' % self.phone_number)
    s.append('Business Name (optional): %s' % self.business_name)
    s.append('Notes (optional): %s' % self.notes)
    return '\n'.join(s)

  def post_data(self, prefix):
    post_data = {}

    post_data['%s_name' % prefix] = self.name
    post_data['%s_address' % prefix] = self.address
    post_data['%s_phone_number' % prefix] = self.phone_number
    post_data['%s_business_name' % prefix] = self.business_name
    post_data['%s_notes' % prefix] = self.notes

    return post_data

class PostmatesAPIException(Exception):

  def __init__(self, message):
    if isinstance(message, str):
      super(PostmatesAPIException, self).__init__(message)
    else:
      super(PostmatesAPIException, self).__init__(message['message'])
      self.kind = message['kind']
      self.code = message['code']

def _parse_date(d):
  if d:
    dt = datetime.strptime(d, '%Y-%m-%dT%H:%M:%SZ')
    return dt.replace(tzinfo=tz.tzutc())
  return d

def _to_local_tz(t):
  from_zone = tz.tzutc()
  to_zone = tz.tzlocal()
  if t:
    return t.astimezone(to_zone)
  return t


