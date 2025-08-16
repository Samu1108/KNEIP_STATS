import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta

# === CONFIGURAZIONE FIREBASE ===
cred = credentials.Certificate("serviceAccountKey.json")  # percorso al file della key
firebase_admin.initialize_app(cred)
db = firestore.client()

# === INPUT DALL'UTENTE ===
data_input = input("Inserisci la data (YYYY-MM-DD): ").strip()
orario_input = input("Inserisci l'orario (HH:MM, 24h): ").strip()
num_adulti = int(input("Quanti adulti eliminare? "))
num_bambini = int(input("Quanti bambini eliminare? "))

# Converte orario in minuti per confronto
h, m = map(int, orario_input.split(":"))
target_minutes = h * 60 + m

# === RECUPERA DOCUMENTI DELLA DATA ===
docs = db.collection("clienti").where("data", "==", data_input).stream()
clienti = [doc.to_dict() | {"id": doc.id} for doc in docs]

if not clienti:
    print("Nessun cliente trovato per la data inserita.")
    exit()

# === ORDINA PER ORARIO PIU' VICINO ===
def orario_to_minutes(orario_str):
    try:
        hh, mm = map(int, orario_str.split(":"))
        return hh*60 + mm
    except:
        return 0

clienti.sort(key=lambda c: abs(orario_to_minutes(c.get("orario","00:00")) - target_minutes))

# === SELEZIONA DA ELIMINARE ===
adulti_elim = 0
bambini_elim = 0
to_delete = []

for c in clienti:
    descr = c.get("descrizione","").lower()
    if "bamb" in descr and bambini_elim < num_bambini:
        to_delete.append(c)
        bambini_elim += 1
    elif "bamb" not in descr and adulti_elim < num_adulti:
        to_delete.append(c)
        adulti_elim += 1
    if adulti_elim >= num_adulti and bambini_elim >= num_bambini:
        break

if not to_delete:
    print("Non ci sono documenti da eliminare in base ai criteri forniti.")
    exit()

# === MOSTRA RIEPILOGO ===
print("Documenti selezionati per eliminazione:")
for c in to_delete:
    print(f"- {c['id']}: {c.get('descrizione','')} ({c.get('orario','')})")

confirm = input("Confermi l'eliminazione di questi documenti? (s/n): ").strip().lower()
if confirm != 's':
    print("Operazione annullata.")
    exit()

# === ELIMINA DOCUMENTI ===
for c in to_delete:
    db.collection("clienti").document(c["id"]).delete()

print(f"Eliminati {len(to_delete)} documenti.")
