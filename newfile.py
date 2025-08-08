from flask import Flask
from threading import Thread
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import csv
from datetime import datetime

API_TOKEN = "7873815642:AAGQgBfsg4O3Qw0pJsdbA4isnprK3JRqX4w"
ID_CANAL = -1002884958871  # Remplace par l'ID de ton canal

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)
user_data = {}

@app.route('/')
def home():
    return "Bot is running!"

@bot.message_handler(commands=['start', 'menu'])
def menu_principal(message):
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("💸 Transférer de l'argent", callback_data="transfert"))
    markup.row(InlineKeyboardButton("📞 Contacter le support", url="https://t.me/TonSupportTelegram"))
    bot.send_message(message.chat.id, "📋 Menu principal :", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id

    if call.data == "transfert":
        markup = InlineKeyboardMarkup()
        for res in ["mtn", "moov", "orange", "wave"]:
            markup.add(InlineKeyboardButton(f"📶 {res.upper()}", callback_data=f"debit_{res}"))
        markup.add(InlineKeyboardButton("⬅️ Retour", callback_data="retour_menu"))
        bot.edit_message_text("Depuis quel réseau souhaitez-vous être débité ?", call.message.chat.id, call.message.id, reply_markup=markup)

    elif call.data.startswith("debit_"):
        reseau = call.data.split("_")[1]
        user_data[user_id] = {"reseau_debit": reseau}
        msg = bot.send_message(call.message.chat.id, "Quel est le numéro à débiter ? (10 chiffres)")
        bot.register_next_step_handler(msg, demander_numero_debit)

    elif call.data.startswith("credit_"):
        reseau = call.data.split("_")[1]
        user_data[user_id]["reseau_credit"] = reseau
        msg = bot.send_message(call.message.chat.id, "Quel est le numéro à créditer ? (10 chiffres)")
        bot.register_next_step_handler(msg, demander_numero_credit)

    elif call.data == "confirmer":
        data = user_data.get(user_id)
        if data:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open("commandes.csv", "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    user_id,
                    call.from_user.username or "Inconnu",
                    data.get("reseau_debit"),
                    data.get("numero_debit"),
                    data.get("reseau_credit"),
                    data.get("numero_credit"),
                    data.get("montant_net"),
                    now
                ])
            # ✅ ENVOI DANS LE CANAL
            recap = (
                f"📤 Vous envoyez au {data['numero_credit']} depuis le {data['numero_debit']}, "
                f"à la date {now}.\n"
                f"💰 Montant : {data['montant_net']} F (frais inclus : {data['montant_brut']} F)"
            )
            bot.send_message(ID_CANAL, recap)
            bot.send_message(call.message.chat.id, "✅ Commande enregistrée avec succès !")
        else:
            bot.send_message(call.message.chat.id, "❌ Aucune commande en cours.")

    elif call.data == "retour_menu":
        menu_principal(call.message)

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

# Lancer le bot dans un thread
def run_bot():
    bot.polling(none_stop=True)

if __name__ == "__main__":
    Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=10000)