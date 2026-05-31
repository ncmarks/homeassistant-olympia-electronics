# Olympia Electronics for Home Assistant

A custom [Home Assistant](https://www.home-assistant.io/) integration for
**Olympia Electronics** smart Wi‑Fi thermostats, talking to the official
Olympia Electronics IoT cloud API.

> ⚠️ This is an **unofficial**, community-maintained integration. It is not
> affiliated with or endorsed by Olympia Electronics. Use at your own risk.

## Features

- 🌡️ Temperature monitoring and target-temperature control
- 🔥 HVAC mode control (Heat / Off) with live action (Heating / Idle / Off)
- 🚿 Independent boiler control via a switch entity
- 📊 Burner state as a binary sensor
- 🟢 Live availability (online/offline), plus RSSI and firmware in attributes
- 🔑 Proactive JWT token refresh (2 min before expiry) with automatic retry on 401
- ⚡ Single cloud poll shared across all entities (every 30s)
- 🏠 **Multi-device support** — all thermostats on your account are discovered and added automatically
- ⚙️ Configurable target-temperature range and step via the integration options
- 🔁 Re-authentication flow when your account password changes (no need to re-add)

## Supported devices

Olympia Electronics wireless Wi‑Fi room thermostats:

| Model | Outputs | Boiler switch |
| --- | --- | --- |
| **BS-851P/KIT** | Burner **and** boiler | ✅ Created |
| **BS-850P/KIT** | Burner only | ❌ Not created (no boiler output) |

The integration reads each thermostat's capabilities from the API, so a
burner-only model simply doesn't get a boiler switch. Tested against
**BS-851P/KIT**; BS-850P/KIT should work too but hasn't been verified on a
real device.

## Entities

Per thermostat, the integration creates (depending on the model):

| Entity | Type | Description |
| --- | --- | --- |
| `climate.<name>` | Climate | Mode (Heat/Off), target temperature, current temperature, HVAC action |
| `switch.<name>_boiler` | Switch | Turn the boiler on/off directly |
| `binary_sensor.<name>_burner` | Binary sensor | Burner (actual flame) running state |

The climate entity also exposes `boiler_on`, `burner_on`, `is_online` and
`rssi` as extra state attributes.

> The boiler switch and burner sensor are only created for thermostats that
> actually report those features, so a model without a boiler won't get them.

## Installation

### Manual

1. Copy the integration files into your Home Assistant config so the folder
   layout is:

   ```
   config/custom_components/olympia_electronics/
   ├── __init__.py
   ├── manifest.json
   ├── config_flow.py
   ├── coordinator.py
   ├── entity.py
   ├── climate.py
   ├── switch.py
   ├── binary_sensor.py
   ├── strings.json
   └── translations/
       └── en.json
   ```

2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and search for **Olympia Electronics**.

### HACS (custom repository)

1. In HACS, open the ⋮ menu (top right) → **Custom repositories**, and add this
   repo's URL with type **Integration**.
2. Search for **Olympia Electronics**, install it, then restart Home Assistant.

## Configuration

This integration is configured via the Home Assistant UI — no YAML needed.

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Olympia Electronics**.
3. Enter your account email and password (the same credentials you use in the
   Olympia Electronics mobile app).

That's it. All thermostats on your account are discovered automatically.

### Options

After setup, open the integration and click **Configure** to tune the climate
entities:

| Option | Default | Description |
| --- | --- | --- |
| Minimum temperature | 10 °C | Lower bound for the target temperature |
| Maximum temperature | 30 °C | Upper bound for the target temperature |
| Temperature step | 0.1 °C | Step/precision used when setting the target (0.1 / 0.5 / 1) |

Saving options reloads the integration so the new range and step take effect
immediately.

### Re-authentication

If your account password changes, the integration triggers a re-authentication
prompt under **Settings → Devices & Services** so you can enter the new
credentials — no need to delete and re-add it.


## Requirements

- Home Assistant **2024.12** or newer
- No external Python dependencies

## Troubleshooting

- **Authentication fails on startup:** double-check the email/password you use
  in the Olympia Electronics mobile app. Errors are logged under the
  `custom_components.olympia_electronics` logger.
- **No entities appear:** make sure at least one thermostat is registered to
  your account; the log will warn if no devices are returned.

Enable debug logging for more detail:

```yaml
logger:
  default: info
  logs:
    custom_components.olympia_electronics: debug
```

## License

[MIT](LICENSE)
