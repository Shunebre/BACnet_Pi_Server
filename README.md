# BACnet Pi Server

Per la versione in inglese leggere [README.en.md](README.en.md).


Questo server BACnet per Raspberry Pi consente di esporre punti come input e output GPIO.

Il server espone le funzionalità BACnet di base configurando la
proprietà `protocolObjectTypesSupported` del dispositivo. L'elenco degli
oggetti viene filtrato in base ai tipi supportati dalla libreria BACpypes
per evitare errori in lettura. Tutti i pin BCM
pari (2–27) vengono configurati come *Binary Input*, mentre i pin dispari
diventano *Binary Output* controllabili tramite la proprietà
`presentValue`. Ogni oggetto viene chiamato `GPIOX`, dove `X` è il numero
del pin e possiede come descrizione `GPIOX Pin X`. Per i *Binary Output*
è disponibile anche la proprietà `polarity` (valori `normal` o `reverse`)
che consente di invertire il comportamento di attivazione.

## Aggiunta di oggetti dinamici

Oltre agli oggetti predefiniti (Binary Input e Binary Output) è possibile
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

È possibile aggiungere anche altri tipi di oggetto. Ad esempio un `AnalogValueObject` può essere descritto così:

```json
  {
    "module": "bacpypes.object",
    "class": "AnalogValueObject",
    "params": {
      "objectIdentifier": ["analogValue", 1],
      "objectName": "EsempioAV",
      "presentValue": 0,
      "statusFlags": [false, false, false, false],
      "outOfService": false,
      "eventState": "normal"
    }
  }
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

Installare le dipendenze con `pip install -r requirements.txt`.
Avviare lo script con:

```bash
./Bacnet-server.py
```

Se il server deve comunicare tramite una VPN, è possibile registrarsi presso un
BBMD specificando l'indirizzo con l'opzione `--bbmd`, ad esempio:

```bash
./Bacnet-server.py --bbmd 10.194.195.1
```

È anche possibile specificare un IP di broadcast personalizzato con
l'opzione `--broadcast-ip`:

```bash
./Bacnet-server.py --broadcast-ip 255.255.255.255
```

È possibile modificare l'ID del dispositivo tramite l'opzione `--device-id`:

```bash
./Bacnet-server.py --device-id 123
```

### Esempio servizio systemd
Un esempio di unita` e` disponibile nella cartella `systemd/` come `bacnet.service`.
Modificare `WorkingDirectory` ed `ExecStart` con i percorsi corretti e abilitare con:
```bash
sudo systemctl enable bacnet.service
```

### Configurazione automatica del servizio

Lo script `install_service.py` genera e avvia l'unità con i parametri
desiderati, ricaricando il daemon e abilitando automaticamente il servizio.
Esempio:

```bash
sudo python3 install_service.py --address 192.168.1.10/24:47808 --device-id 123
```

Se l'avvio va a buon fine viene mostrato `BACnet_Pi_Server avviato con successo`.
In caso contrario appare `BACnet_Pi_Server fallito avviamento`.

### Gestione delle versioni


Il numero di versione è contenuto nel file `VERSION`. Ogni modifica al codice
deve incrementare la versione di **0.0.1** per mantenere allineate le
proprietà `applicationSoftwareVersion` e `firmwareRevision` esposte dal
dispositivo BACnet.
