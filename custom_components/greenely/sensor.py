"""Greenely sensors"""
from datetime import datetime, timedelta
import json

import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.entity import Entity

from .api import GreenelyApi

from .const import (DOMAIN, SENSOR_DAILY_USAGE_NAME, SENSOR_HOURLY_USAGE_NAME, SENSOR_DAILY_PRODUCTION_NAME,
                    SENSOR_SOLD_NAME, SENSOR_PRICES_NAME, CONF_HOURLY_USAGE,
                    CONF_DAILY_USAGE, CONF_DAILY_PRODUCTION, CONF_SOLD, CONF_PRICES, CONF_DATE_FORMAT,
                    CONF_TIME_FORMAT, CONF_USAGE_DAYS, CONF_PRODUCTION_DAYS, CONF_SOLD_MEASURE,
                    CONF_SOLD_DAILY, CONF_HOURLY_OFFSET_DAYS, CONF_FACILITY_ID, CONF_HOMEKIT_COMPATIBLE)

NAME = DOMAIN
ISSUEURL = "https://github.com/linsvensson/sensor.greenely/issues"

STARTUP = f"""
-------------------------------------------------------------------
{NAME}
This is a custom component
If you have any issues with this you need to open an issue here:
{ISSUEURL}
-------------------------------------------------------------------
"""

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_EMAIL):
    cv.string,
    vol.Required(CONF_PASSWORD):
    cv.string,
    vol.Optional(CONF_DAILY_USAGE, default=True):
    cv.boolean,
    vol.Optional(CONF_HOURLY_USAGE, default=False):
    cv.boolean,
    vol.Optional(CONF_DAILY_PRODUCTION, default=False):
    cv.boolean,
    vol.Optional(CONF_SOLD, default=False):
    cv.boolean,
    vol.Optional(CONF_PRICES, default=True):
    cv.boolean,
    vol.Optional(CONF_USAGE_DAYS, default=10):
    cv.positive_int,
    vol.Optional(CONF_PRODUCTION_DAYS, default=10):
    cv.positive_int,
    vol.Optional(CONF_SOLD_MEASURE, default=2):
    cv.positive_int,
    vol.Optional(CONF_SOLD_DAILY, default=False):
    cv.boolean,
    vol.Optional(CONF_DATE_FORMAT, default='%b %d %Y'):
    cv.string,
    vol.Optional(CONF_TIME_FORMAT, default='%H:%M'):
    cv.string,
    vol.Optional(CONF_HOURLY_OFFSET_DAYS, default=1):
    cv.positive_int,
    vol.Optional(CONF_FACILITY_ID, default='primary'):
    cv.string,
    vol.Optional(CONF_HOMEKIT_COMPATIBLE, default=False):
    cv.boolean,
})

SCAN_INTERVAL = timedelta(minutes=60)


async def async_setup_platform(hass,
                               config,
                               async_add_entities,
                               discovery_info=None):
    email = config.get(CONF_EMAIL)
    password = config.get(CONF_PASSWORD)

    date_format = config.get(CONF_DATE_FORMAT)
    time_format = config.get(CONF_TIME_FORMAT)
    show_daily_usage = config.get(CONF_DAILY_USAGE)
    show_hourly_usage = config.get(CONF_HOURLY_USAGE)
    show_daily_production = config.get(CONF_DAILY_PRODUCTION)
    show_sold = config.get(CONF_SOLD)
    show_prices = config.get(CONF_PRICES)
    usage_days = config.get(CONF_USAGE_DAYS)
    production_days = config.get(CONF_PRODUCTION_DAYS)
    sold_measure = config.get(CONF_SOLD_MEASURE)
    sold_daily = config.get(CONF_SOLD_DAILY)
    hourly_offset_days = config.get(CONF_HOURLY_OFFSET_DAYS)
    facility_id = config.get(CONF_FACILITY_ID)
    homekit_compatible = config.get(CONF_HOMEKIT_COMPATIBLE)

    api = GreenelyApi(email, password, facility_id)

    _LOGGER.debug('Setting up sensor(s)...')

    sensors = []
    if show_daily_usage:
        sensors.append(
            GreenelyDailyUsageSensor(SENSOR_DAILY_USAGE_NAME, api, usage_days,
                                     date_format, time_format))
    if show_hourly_usage:
        sensors.append(
            GreenelyHourlyUsageSensor(SENSOR_HOURLY_USAGE_NAME, api,
                                      hourly_offset_days, date_format,
                                      time_format))
    if show_daily_production:    
        sensors.append(
            GreenelyDailyProductionSensor(SENSOR_DAILY_PRODUCTION_NAME, api, production_days,
                                        date_format, time_format))
    if show_sold:
        sensors.append(
            GreenelySoldSensor(SENSOR_SOLD_NAME, api, sold_measure, sold_daily,
                               date_format))
    if show_prices:
        sensors.append(
            GreenelyPricesSensor(SENSOR_PRICES_NAME, api, date_format,
                                 time_format, homekit_compatible))
    async_add_entities(sensors, True)


class GreenelyPricesSensor(Entity):

    def __init__(self, name, api, date_format, time_format, homekit_compatible):
        self._name = name
        self._icon = "mdi:account-cash"
        self._state = 0
        self._state_attributes = {}
        self._unit_of_measurement = 'SEK/kWh' if homekit_compatible != True else '°C'
        self._date_format = date_format
        self._time_format = time_format
        self._homekit_compatible = homekit_compatible
        self._api = api

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._state_attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    def update(self):
        """Update state and attributes."""
        _LOGGER.debug('Checking jwt validity...')
        if self._api.check_auth():
            data = self._api.get_price_data()
            totalCost = 0
            if data:
                for d, value in data.items():
                    cost = value['cost']
                    if cost != None:
                        totalCost += cost
                self._state_attributes['current_month'] = round(totalCost / 100000)
            spot_price_data = self._api.get_spot_price()
            if spot_price_data:
                _LOGGER.debug('Fetching daily prices...')
                today = datetime.now().replace(hour=0,
                                               minute=0,
                                               second=0,
                                               microsecond=0)
                todaysData = []
                tomorrowsData = []
                yesterdaysData = []
                for d in spot_price_data['data']:
                    timestamp = datetime.strptime(
                        spot_price_data['data'][d]['localtime'],
                        '%Y-%m-%d %H:%M')
                    if timestamp.date() == today.date():
                        if spot_price_data['data'][d]['price'] != None:
                            todaysData.append(
                                self.make_attribute(spot_price_data, d))
                    elif timestamp.date() == (today.date() +
                                              timedelta(days=1)):
                        if spot_price_data['data'][d]['price'] != None:
                            tomorrowsData.append(
                                self.make_attribute(spot_price_data, d))
                    elif timestamp.date() == (today.date() -
                                              timedelta(days=1)):
                        if spot_price_data['data'][d]['price'] != None:
                            yesterdaysData.append(
                                self.make_attribute(spot_price_data, d))
                self._state_attributes['current_day'] = todaysData
                self._state_attributes['next_day'] = tomorrowsData
                self._state_attributes['previous_day'] = yesterdaysData
        else:
            _LOGGER.error('Unable to log in!')

    def make_attribute(self, response, value):
        if response:
            newPoint = {}
            today = datetime.now()
            price = response['data'][value]['price']
            dt_object = datetime.strptime(response['data'][value]['localtime'],
                                          '%Y-%m-%d %H:%M')
            newPoint['date'] = dt_object.strftime(self._date_format)
            newPoint['time'] = dt_object.strftime(self._time_format)
            if price != None:
                rounded = self.format_price(price)
                newPoint['price'] = rounded
                if dt_object.hour == today.hour and dt_object.day == today.day:
                    self._state = rounded
            else:
                newPoint['price'] = 0
            return newPoint

    def format_price(self, price):
        if self._homekit_compatible == True:
            return round(price / 1000)
        else:
             return round(((price / 1000) / 100), 4)

    def make_data_attribute(self, name, response, nameOfPriceAttr):
        if response:
            points = response.get('points', None)
            data = []
            for point in points:
                price = point[nameOfPriceAttr]
                if price != None:
                    newPoint = {}
                    dt_object = datetime.utcfromtimestamp(point['timestamp'])
                    newPoint['date'] = dt_object.strftime(self._date_format)
                    newPoint['time'] = dt_object.strftime(self._time_format)
                    newPoint['price'] = str(price / 100)
                    data.append(newPoint)
            self._state_attributes[name] = data


class GreenelyDailyUsageSensor(Entity):

    def __init__(self, name, api, usage_days, date_format, time_format):
        self._name = name
        self._icon = "mdi:power-socket-eu"
        self._state = 0
        self._state_attributes = {'state_class':'measurement','last_reset':'1970-01-01T00:00:00+00:00'}
        self._unit_of_measurement = 'kWh'
        self._usage_days = usage_days
        self._date_format = date_format
        self._time_format = time_format
        self._api = api
        self._device_class = 'energy'

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._state_attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return self._device_class

    def update(self):
        _LOGGER.debug('Checking jwt validity...')
        if self._api.check_auth():
            # Get todays date
            today = datetime.now().replace(hour=0,
                                           minute=0,
                                           second=0,
                                           microsecond=0)
            _LOGGER.debug('Fetching daily usage data...')
            data = []
            startDate = today - timedelta(days=self._usage_days)
            response = self._api.get_usage(startDate, today, False)
            if response:
                data = self.make_attributes(today, response)
            self._state_attributes['data'] = data
        else:
            _LOGGER.error('Unable to log in!')

    def make_attributes(self, today, response):
        yesterday = today - timedelta(days=1)
        data = []
        keys = iter(response)
        if keys != None:
            for k in keys:
                daily_data = {}
                dateTime = datetime.strptime(response[k]['localtime'],
                                             '%Y-%m-%d %H:%M')
                daily_data['localtime'] = dateTime.strftime(self._date_format)
                usage = response[k]['usage']
                if (dateTime == yesterday):
                    self._state = usage / 1000 if usage != None else 0
                daily_data['usage'] = (usage / 1000) if usage != None else 0
                data.append(daily_data)
        return data


class GreenelyHourlyUsageSensor(Entity):

    def __init__(self, name, api, hourly_offset_days, date_format,
                 time_format):
        self._name = name
        self._icon = "mdi:power-socket-eu"
        self._state = 0
        self._state_attributes = {'state_class':'measurement','last_reset':'1970-01-01T00:00:00+00:00'}
        self._unit_of_measurement = 'kWh'
        self._date_format = date_format
        self._time_format = time_format
        self._hourly_offset_days = hourly_offset_days
        self._api = api
        self._device_class = 'energy'

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._state_attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return self._device_class

    def update(self):
        _LOGGER.debug('Checking jwt validity...')
        if self._api.check_auth():
            # Get todays date
            today = datetime.now().replace(hour=0,
                                           minute=0,
                                           second=0,
                                           microsecond=0)
            _LOGGER.debug('Fetching hourly usage data...')
            data = []
            startDate = today - timedelta(days=self._hourly_offset_days)
            response = self._api.get_usage(startDate, today, True)
            if response:
                data = self.make_attributes(datetime.now(), response)
            self._state_attributes['data'] = data
        else:
            _LOGGER.error('Unable to log in!')

    def make_attributes(self, today, response):
        yesterday = today - timedelta(days=1)
        data = []
        keys = iter(response)
        if keys != None:
            for k in keys:
                hourly_data = {}
                dateTime = datetime.strptime(response[k]['localtime'],
                                             '%Y-%m-%d %H:%M')
                hourly_data['localtime'] = dateTime.strftime(
                    self._date_format) + ' ' + dateTime.strftime(
                        self._time_format)
                usage = response[k]['usage']
                if (dateTime.hour == yesterday.hour
                        and dateTime.day == yesterday.day
                        and dateTime.month == yesterday.month
                        and dateTime.year == yesterday.year):
                    self._state = usage / 1000 if usage != None else 0
                hourly_data['usage'] = (usage / 1000) if usage != None else 0
                data.append(hourly_data)
        return data


class GreenelySoldSensor(Entity):

    def __init__(self, name, api, sold_measure, sold_daily, date_format):
        self._name = name
        self._icon = "mdi:solar-power"
        self._state = 0
        self._state_attributes = {}
        self._unit_of_measurement = 'kWh'
        self._date_format = date_format
        self._sold_measure = sold_measure
        self._sold_daily = sold_daily
        self._api = api

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._state_attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    def update(self):
        _LOGGER.debug('Checking jwt validity...')
        if self._api.check_auth():
            _LOGGER.debug('Fetching sold data...')
            response = self._api.get_sold(self._sold_measure, self._sold_daily)
            if response:
                self.make_attribute(response)
        else:
            _LOGGER.error('Unable to log in!')

    def make_attribute(self, response):
        total_sold = 0
        months = []
        jsonObject = json.loads(json.dumps(response))
        for key in jsonObject:
            data = {}
            value = jsonObject[key]
            usage = value['usage']
            date = datetime.strptime(value['localtime'], "%Y-%m-%d %H:%M")
            data['date'] = date.strftime(self._date_format)
            data['usage'] = str(usage / 1000) if usage != 0 else 0
            data['is_complete'] = value['is_complete']

            total_sold += usage
            if data:
                months.append(data)
        self._state = str(total_sold / 1000) if total_sold != 0 else 0
        self._state_attributes['sold_data'] = months


class GreenelyDailyProductionSensor(Entity):

    def __init__(self, name, api, production_days, date_format, time_format):
        self._name = name
        self._icon = "mdi:power-socket-eu"
        self._state = 0
        self._state_attributes = {'state_class':'measurement','last_reset':'1970-01-01T00:00:00+00:00'}
        self._unit_of_measurement = 'kWh'
        self._production_days = production_days
        self._date_format = date_format
        self._time_format = time_format
        self._api = api
        self._device_class = 'energy'

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._state_attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return self._device_class

    def update(self):
        _LOGGER.debug('Checking jwt validity...')
        if self._api.check_auth():
            # Get todays date
            today = datetime.now().replace(hour=0,
                                           minute=0,
                                           second=0,
                                           microsecond=0)
            _LOGGER.debug('Fetching daily production data...')
            data = []
            startDate = today - timedelta(days=(self._production_days - 1))
            endDate = today + timedelta(days=1)
            response = self._api.get_produced_electricity(startDate, endDate, False)
            if response:
                data = self.make_attributes(today, response)
            self._state_attributes['data'] = data
        else:
            _LOGGER.error('Unable to log in!')

    def make_attributes(self, today, response):
        data = []
        keys = iter(response)
        if keys != None:
            for k in keys:
                daily_data = {}
                dateTime = datetime.strptime(response[k]['localtime'],
                                             '%Y-%m-%d %H:%M')
                daily_data['localtime'] = dateTime.strftime(self._date_format)
                production = response[k]['value']
                if (dateTime == today):
                    self._state = production / 1000 if production != None else 0
                daily_data['production'] = (production / 1000) if production != None else 0
                data.append(daily_data)
        return data