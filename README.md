# BACnet Pi Server

Questo server BACnet per Raspberry Pi consente di esporre punti come input e output GPIO.

Il punto `Operation_Mode` è un oggetto *Multi-State Value* con due stati:
"Input" e "Output". Scrivendo questo valore si può commutare la modalità dei
pin di uscita. All'avvio i pin di uscita vengono configurati in base al valore
predefinito di `Operation_Mode`.

Il server espone le funzionalità BACnet di base configurando la
proprietà `protocolObjectTypesSupported` del dispositivo. Inoltre
`Operation_Mode` accetta scritture tramite il servizio `WriteProperty`.

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
      "presentValue": 0,
      "statusFlags": [false, false, false, false],
      "outOfService": false,
      "eventState": "normal"
    }
  }
]
```

Il sistema importa dinamicamente il modulo e la classe indicati e aggiunge l'oggetto
all'applicazione. In questo modo è possibile utilizzare qualsiasi tipo di oggetto fornito
dalle librerie installate, inclusi quelli elencati nella richiesta (Alarm, Schedule, ecc.).
Se nel file JSON `objectIdentifier` è definito come lista, lo script lo converte
automaticamente in una tupla prima di creare l'oggetto.
Se viene fornito l'attributo `statusFlags` come lista di quattro valori
booleani, questo viene convertito automaticamente nell'oggetto `StatusFlags` di
bacpypes.

## Esecuzione

Assicurarsi che le dipendenze (RPi.GPIO e bacpypes) siano installate.
Avviare lo script con:

```bash
python Bacnet-server.py
```

Se il server deve comunicare tramite una VPN, è possibile registrarsi presso un
BBMD specificando l'indirizzo con l'opzione `--bbmd`, ad esempio:

```bash
python Bacnet-server.py --bbmd 10.194.195.1
```

È anche possibile impostare la variabile d'ambiente `BACNET_BBMD` con
l'indirizzo del BBMD, utile quando il server viene avviato tramite systemd.

Esempio di unità systemd:

```ini
[Service]
Environment="BACNET_BBMD=10.194.195.1"
ExecStart=/usr/bin/python3 /percorso/Bacnet-server.py
```

### Gestione delle versioni

Il numero di versione è contenuto nel file `VERSION`. Ogni modifica al codice
deve incrementare la versione di **0.0.1** per mantenere allineate le
proprietà `applicationSoftwareVersion` e `firmwareRevision` esposte dal
dispositivo BACnet.
