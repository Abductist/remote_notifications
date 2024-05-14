"""Support for remote notifications via webhooks and events."""
import json
import logging

import requests
import voluptuous as vol

import aiohttp

from homeassistant.const import (
	CONF_WEBHOOK_ID,
	CONF_EVENT
)
import homeassistant.helpers.config_validation as cv

from homeassistant.config import async_hass_config_yaml
from homeassistant.components import webhook

_LOGGER = logging.getLogger(__name__)

DOMAIN = "remote_notifications"
'''
CONFIG_SCHEMA = vol.Schema(
	{
		DOMAIN: vol.Schema(
			{
				vol.Required("target_service_map"): cv.has_at_least_one_key,
				vol.Required(Any(CONF_WEBHOOK_ID, CONF_EVENT, msg=f"{CONF_EVENT} or {CONF_WEBHOOK_ID} is required")): cv.string
			}
		)
	},
	extra=vol.ALLOW_EXTRA,
)
'''
async def handle_event_with_hass_config(event, hass, config):
	_LOGGER.debug("Received remote notification")
	return await handle_data(event.data, hass, config)

async def handle_webhook_with_config(hass, webhook_id, request, config):
	"""Handle webhook callback."""
	_LOGGER.debug('Received Remote Notifier webhook.')
	try:
		data = await request.json()
	except ValueError:
		_LOGGER.warn('Issue decoding webhook: ' + request)
		return None
	
	return await handle_data(data, hass, config)
	
async def handle_data(data, hass, config):
	configured_target_service_map = config["target_service_map"]

	"""
	This may be slightly slower as we load the configuration on
	the fly each time we trigger notifications
	"""
	configFile = await async_hass_config_yaml(hass)
	configured_target_service_map = configFile[DOMAIN]["target_service_map"]
	
	target_services = []
	if "targets" in data:
		for target in data['targets']:
			if target in configured_target_service_map and configured_target_service_map[target] not in target_services:
				target_services.append(configured_target_service_map[target])

	if len(target_services) == 0:
		target_services.append(configured_target_service_map["conrad"])
	
	if "clearNotification" in data and data["clearNotification"] == True and "tag" in data:
		notification_message = 'clear_notification'
	else:
		notification_message = data["message"]
		
	notification_data = {
		"push": {
			"sound": {
				"name": 'default'
			}
		}
	}
	if "subtitle" in data:
		notification_data["subtitle"] = data["subtitle"]
	if "url" in data:
		notification_data["url"] = data["url"]
	if "actions" in data:
		notification_data["actions"] = data["actions"]
	if "category" in data:
		notification_data["group"] = data["category"]
	if "tag" in data:
		notification_data["tag"] = data["tag"]
	if "image" in data:
		notification_data["image"] = data["image"]
	if "video" in data:
		notification_data["video"] = data["video"]
	if "audio" in data:
		notification_data["audio"] = data["audio"]
	if "interruptionLevel" in data:
		notification_data["push"]["interruption-level"] = data["interruptionLevel"]
	if "critical" in data and data["critical"] is True:
		notification_data["push"]["sound"]["critical"] = data["critical"]
		notification_data["push"]["sound"]["volume"] = data["critical"]
	else:
		if "sound" in data and data["sound"] == "none":
			notification_data["push"]["sound"] = "none"
		else:
			notification_data["push"]["sound"]["critical"] = 0
			notification_data["push"]["sound"]["volume"] = 0

	notification = {
		"message": notification_message,
		"data": notification_data
	}
	if "title" in data:
		notification["title"] = data["title"]
	
	
	for target_service in target_services:
		target_service_array = target_service.split(".")
		domain = target_service_array[0]
		service = target_service_array[1]
		await hass.services.async_call(domain, service, notification)

async def async_setup(hass, config):
	_LOGGER.debug('Initiating Remote Notifications Webhooks!')
	async def handle_event(event):
		return await handle_event_with_hass_config(event, hass, config[DOMAIN])
	async def handle_webhook(hass, webhook_id, request):
		return await handle_webhook_with_config(hass, webhook_id, request, config[DOMAIN])

	if CONF_EVENT in config[DOMAIN]:
		event_type = config[DOMAIN][CONF_EVENT]
		hass.bus.async_listen(event_type, handle_event)
	if CONF_WEBHOOK_ID in config[DOMAIN]:
		webhook_id = config[DOMAIN][CONF_WEBHOOK_ID]
		webhook.async_register(
			hass, DOMAIN, "Remote Notifications", webhook_id, handle_webhook
		)
	return True
