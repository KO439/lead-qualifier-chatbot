"""
Publie le score de qualification sur un broker MQTT public.
"""
import json
import paho.mqtt.client as mqtt

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC = "leadqualifier/score"


def publish_score(score: int, category: str, priorite: str = ""):
    try:
        client = mqtt.Client()
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=5)

        payload = json.dumps({
            "score": score,
            "category": category,
            "priorite": priorite,
        })

        client.publish(MQTT_TOPIC, payload)
        client.disconnect()
        print(f"[mqtt] Score publié : {payload}")
    except Exception as e:
        print(f"[mqtt] Erreur publication : {e}")
