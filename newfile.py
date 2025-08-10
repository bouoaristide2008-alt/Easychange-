from flask import Flask
from threading import Thread
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import csv
from datetime import datetime
import json, os

# === CONFIGURATION ===
API_TOKEN = "7873815642:AAGQgBfsg4O3Qw0pJsdbA4isnprK3JRqX4w"
ID_CANAL = -1002884958871  # Ton canal
ADMIN_ID = 6357925694       # Mets ici TON ID Telegram

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

user_data = {}

# === COMPTEUR D'ABONNÉS ===
FICHIER_USERS = "users.json"
if os.path.exists(FICHIER_USERS):
    with open(FICHIER_USERS, "r") as f:
        abonnes = set(json.load(f))
else:
    abonnes = set()

# === SUPPORT INTERACTIF ===
support_steps = {}

@app.route('/')
def home():
    return "Bot is running!"

@bot.message_handler(commands=['start', 'menu'])
def menu_principal(message):
    abonnes.add(message.from_user.id)
    with open(FICHIER_USERS, "w") as f:
        json.dump(list(abonnes), f)

    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("💸 Transférer de l'argent", callback_data="transfert"))
    markup.row(InlineKeyboardButton("📞 Contacter le support", callback_data="support_menu"))
    bot.send_message(message.chat.id, "📋 Menu principal :", reply_markup=markup)

@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id == ADMIN_ID:
        bot.reply_to(message, f"📊 Nombre total d'abonnés : {len(abonnes)}")
    else:
        bot.reply_to(message, "⛔ Tu n'as pas la permission de voir ")
        @bot.message_handler(commands=['abonnes'])
def nombre_abonnes(message):
    bot.reply_to(message, f"📊 Nombre total d'abonnés : {len(abonnes)}")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    data = call.data

    if data == "transfert":
        markup = InlineKeyboardMarkup()
        for res in ["mtn", "moov", "orange", "wave"]:
            markup.add(InlineKeyboardButton(f"📶 {res.upper()}", callback_data=f"debit_{res}"))
        markup.add(InlineKeyboardButton("⬅️ Retour", callback_data="retour_menu"))
        bot.edit_message_text("Depuis quel réseau souhaitez-vous être débité ?", call.message.chat.id, call.message.id, reply_markup=markup)

    elif data.startswith("debit_"):
        reseau = data.split("_")[1]
        user_data[user_id] = {"reseau_debit": reseau}
        msg = bot.send_message(call.message.chat.id, "Quel est le numéro à débiter ? (10 chiffres)")
        bot.register_next_step_handler(msg, demander_numero_debit)

    elif data.startswith("credit_"):
        reseau = data.split("_")[1]
        user_data[user_id]["reseau_credit"] = reseau
        msg = bot.send_message(call.message.chat.id, "Quel est le numéro à créditer ? (10 chiffres)")
        bot.register_next_step_handler(msg, demander_numero_credit)

    elif data == "confirmer":
        data_cmd = user_data.get(user_id)
        if data_cmd:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open("commandes.csv", "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    user_id,
                    call.from_user.username or "Inconnu",
                    data_cmd.get("reseau_debit"),
                    data_cmd.get("numero_debit"),
                    data_cmd.get("reseau_credit"),
                    data_cmd.get("numero_credit"),
                    data_cmd.get("montant_net"),
                    now
                ])
            recap = (
                f"📤 Vous envoyez au {data_cmd['numero_credit']} depuis le {data_cmd['reseau_debit']}, "
                f"à la date {now}.\n"
                f"💰 Montant : {data_cmd['montant_net']} F (frais inclus : {data_cmd['montant_brut']} F)"
            )
            bot.send_message(ID_CANAL, recap)
            bot.send_message(call.message.chat.id, "✅ Commande enregistrée avec succès !")
        else:
            bot.send_message(call.message.chat.id, "❌ Aucune commande en cours.")

    elif data == "retour_menu":
        menu_principal(call.message)

    elif data == "support_menu":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📦 Suivre ma commande", callback_data="support_suivi"))
        markup.add(InlineKeyboardButton("💸 Problème de paiement", callback_data="support_paiement"))
        markup.add(InlineKeyboardButton("❓ Autre question", callback_data="support_autre"))
        markup.add(InlineKeyboardButton("⬅️ Retour au menu", callback_data="retour_menu"))
        bot.edit_message_text("📞 Choisissez une option de support :", call.message.chat.id, call.message.id, reply_markup=markup)

    elif data in ["support_suivi", "support_paiement", "support_autre"]:
        support_steps[user_id] = {"type": data, "step": 1}
        bot.edit_message_text("Merci de décrire votre problème en détail. Vous pouvez aussi ajouter des numéros, dates, captures, etc.", call.message.chat.id, call.message.id)

@bot.message_handler(func=lambda message: message.from_user.id in support_steps)
def process_support_message(message):
    user_id = message.from_user.id
    info = support_steps[user_id]

    if info["step"] == 1:
        info["description"] = message.text
        info["step"] = 2
        bot.send_message(user_id, "Voulez-vous ajouter un numéro de commande, une capture d'écran, ou autre détail ?\nEnvoyez-le ou tapez 'non' pour passer.")
    elif info["step"] == 2:
        if message.text.lower() != "non":
            info["details"] = message.text
        else:
            info["details"] = "Aucun détail supplémentaire"
        info["step"] = 3
        bot.send_message(user_id, "Merci ! Votre message a bien été reçu. Notre support va vous répondre bientôt.")

        support_type = info["type"]
        desc = info.get("description", "Pas de description")
        details = info.get("details", "")
        texte = (
            f"📩 *Nouvelle demande de support*\n"
            f"Type : {support_type}\n"
            f"Utilisateur : @{message.from_user.username or 'Inconnu'} ({user_id})\n\n"
            f"Description : {desc}\n"
            f"Détails : {details}"
        )
        bot.send_message(ID_CANAL, texte, parse_mode="Markdown")

        del support_steps[user_id]

def demander_numero_debit(message):
    numero = message.text.strip()
    user_id = message.from_user.id
    if not numero.isdigit() or len(numero) != 10:
        msg = bot.send_message(message.chat.id, "❌ Numéro invalide (10 chiffres).")
        bot.register_next_step_handler(msg, demander_numero_debit)
        return
    prefix = numero[:2]
    valid_prefix = ["05", "01", "07"]
    if prefix not in valid_prefix:
        msg = bot.send_message(message.chat.id, "❌ Numéro invalide (doit commencer par 05, 01 ou 07).")
        bot.register_next_step_handler(msg, demander_numero_debit)
        return
    user_data[user_id]["numero_debit"] = numero
    markup = InlineKeyboardMarkup()
    for res in ["mtn", "moov", "orange", "wave"]:
        markup.add(InlineKeyboardButton(f"📲 {res.upper()}", callback_data=f"credit_{res}"))
    bot.send_message(message.chat.id, "Vers quel réseau souhaitez-vous envoyer l’argent ?", reply_markup=markup)

def demander_numero_credit(message):
    numero = message.text.strip()
    user_id = message.from_user.id
    if not numero.isdigit() or len(numero) != 10:
        msg = bot.send_message(message.chat.id, "❌ Numéro invalide (10 chiffres).")
        bot.register_next_step_handler(msg, demander_numero_credit)
        return
    user_data[user_id]["numero_credit"] = numero
    msg = bot.send_message(message.chat.id, "💵 Entrez le montant (min 200F, termine par 0) :")
    bot.register_next_step_handler(msg, demander_montant)

def demander_montant(message):
    user_id = message.from_user.id
    montant = message.text.strip()
    if not montant.isdigit():
        msg = bot.send_message(message.chat.id, "❌ Entrez un montant valide.")
        bot.register_next_step_handler(msg, demander_montant)
        return
    montant = int(montant)
    if montant < 200 or str(montant)[-1] != "0":
        msg = bot.send_message(message.chat.id, "❌ Montant doit être ≥ 200F et se terminer par 0.")
        bot.register_next_step_handler(msg, demander_montant)
        return
    frais = int(montant * 0.05)
    montant_net = montant + frais
    user_data[user_id]["montant_brut"] = montant_net
    user_data[user_id]["montant_net"] = montant
    data = user_data[user_id]
    recap = (
        f"🧾 *Récapitulatif* :\n"
        f"📤 Depuis : *{data['reseau_debit'].upper()}* | {data['numero_debit']}\n"
        f"📥 Vers : *{data['reseau_credit'].upper()}* | {data['numero_credit']}\n"
        f"💰 Montant : *{montant}* F + *5%* = *{montant_net}* F\n\n"
        f"✅ Confirmer cette commande ?"
    )
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("✅ Confirmer", callback_data="confirmer"),
        InlineKeyboardButton("❌ Annuler", callback_data="retour_menu")
    )
    bot.send_message(message.chat.id, recap, parse_mode="Markdown", reply_markup=markup)

# Lancer le bot dans un thread dès le démarrage (compatible Gunicorn)
def run_bot():
    bot.polling(none_stop=True)

Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
