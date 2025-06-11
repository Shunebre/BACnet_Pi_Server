# BACnet Pi Server

Questo server BACnet per Raspberry Pi consente di esporre punti come input e output GPIO.

## Aggiunta di oggetti dinamici

Oltre agli oggetti predefiniti (Binary Input, Binary Output e Multi-State Value) è possibile
aggiungere ulteriori oggetti definendoli in un file `objects.json` posizionato nella stessa
cartella dello script.

Il file deve contenere una lista di oggetti con i seguenti campi:

```json
[
  {
    "module": "bacpypes.object",
    "class": "BinaryInputObject",
    "params": {
      "objectIdentifier": ["binaryInput", 2],
      "objectName": "EsempioBI",
      "presentValue": 0
    }
  }
]
```

Il sistema importa dinamicamente il modulo e la classe indicati e aggiunge l'oggetto
all'applicazione. In questo modo è possibile utilizzare qualsiasi tipo di oggetto fornito
 dalle librerie installate, inclusi quelli elencati nella richiesta (Alarm, Schedule, ecc.).

## Esecuzione

Assicurarsi che le dipendenze (RPi.GPIO e bacpypes) siano installate.
Avviare lo script con:

```bash
python Bacnet-server.py
```
