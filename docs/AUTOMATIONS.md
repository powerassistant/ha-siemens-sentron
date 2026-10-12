# Everyday automations from measured power

[Back to the overview](../README.md)

## Know when laundry is finished

A washing machine or tumble dryer can be monitored through its circuit's active-power sensor even without a native smart-appliance integration. The circuit needs to be measured by a supported device, and the appliance's load must be distinguishable from other loads on that circuit.

![Power-based completion step in the Home Assistant automation editor](screenshots/laundry-automation.png)

The screenshot shows the completion step from an example installation: power below **3 W for one minute**, followed by changes to boolean helpers. It does **not** show a complete notification workflow. Configure the start detection, running-state condition and notification action separately.

## A practical start / finish workflow

Create two Toggle helpers, for example **Washing machine running** and **Washing machine finished**. Use independent helpers and automations for a tumble dryer.

| Stage | Trigger or condition | Action |
| --- | --- | --- |
| Recognize a start | Power exceeds a suitable running threshold for a sustained period | Turn the running helper on and reset the finished helper |
| Recognize completion | Power stays below a suitable standby threshold; the running helper must already be on | Turn running off and finished on |
| Notify | The finished helper changes from off to on | Send “Laundry is finished” through the selected notification action |

Build this under **Settings → Automations & scenes** with the visual editor. Choose the circuit's **Power Active** entity as the numeric-state source. No Modbus register configuration is needed for the supported sensor.

For the notification, use a configured mobile-app notification action, a speaker announcement through the relevant integration, or a persistent Home Assistant notification. The finished helper can also drive a dashboard indicator. Reset that indicator deliberately, for example when starting the next cycle or acknowledging the message.

## Tune it to the appliance

The screenshot's **3 W / one minute** setting is an illustration, not a universal recommendation. Observe complete cycles before choosing thresholds. A higher start threshold, a lower finish threshold and suitable hold times reduce flickering between states, but cannot by themselves distinguish every programme pause from completion.

Account for washing-machine pauses, dryer anti-crease cycles and standby behaviour. Consider a minimum cycle duration or an additional signal when the power profile alone is ambiguous. On a shared circuit, another load may hide the standby transition or look like a new cycle.

Use measured power, not apparent power or a requested charger setpoint. Make sure the threshold uses the sensor's actual unit. Do not convert missing readings to zero in an intermediate template.

## Restart and missed-event behaviour

Home Assistant numeric-state triggers depend on entering the specified numeric range; they are not continuous “run while below” checks. Waiting periods using `for` do not survive an automation reload or a Home Assistant restart. Decide how a running helper and an interrupted cycle should be reconciled after restart, and test that scenario rather than promising guaranteed delivery. See the [numeric-state trigger documentation](https://www.home-assistant.io/docs/automation/trigger/#numeric-state-trigger).

## Other uses

The same measurements can support user-configured alerts for an appliance left running, unexpectedly high standby consumption or an unusually long operating period. Breaker state, connection status and RCM/alarm entities can support additional notifications where the device profile exposes them.

These are monitoring and convenience workflows, not certified protection. Do not use an automation notification as proof that a circuit is safe to work on. See the [safety notice](../DISCLAIMER.md).
