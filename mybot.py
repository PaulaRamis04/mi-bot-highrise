from __future__ import annotations
import json, asyncio, random
from typing import Dict, Any, Optional, List
from highrise import (
    BaseBot, Position, SessionMetadata, User, CurrencyItem, AnchorPosition
)

DATA_FILE = "talentbot-data.json"

EMOTES = {
    "1": "emote-wave", "2": "emote-bow", "3": "emote-think", "4": "emote-confused",
    "5": "emote-float", "6": "emote-sad", "7": "emote-yes", "8": "emote-no",
    "9": "emote-laughing", "10": "emote-kiss", "11": "emote-curtsy", "12": "emote-snowball",
    "13": "emote-hot", "14": "emote-cold", "15": "emote-shy"
}

class CrewBot(BaseBot):
    def __init__(self) -> None:
        super().__init__()
        self.bot_id = None
        self.owner_id = None
        self.data = {"roles": {}, "jueces": [], "teleports": {}, "names": {}}
        self.talent_queue: List[User] = []
        self.current_performer: Optional[User] = None
        self.looping_users = {} 
        self._load_data()

    def _load_data(self):
        try:
            with open(DATA_FILE, "r") as f:
                self.data.update(json.load(f))
        except: pass

    def _save_data(self):
        with open(DATA_FILE, "w") as f: json.dump(self.data, f, indent=2)

    async def _get_role(self, user: User) -> str:
        if user.id == self.owner_id: return "owner"
        rol_db = self.data.get("roles", {}).get(user.id, "user")
        if user.id in self.data.get("jueces", []): return "juez"
        return rol_db

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        self.bot_id = session_metadata.user_id
        self.owner_id = session_metadata.room_info.owner_id
        asyncio.create_task(self.emote_loop_task())
        print("🎭 BOT SUPREMO ONLINE - Todo activado")

    async def emote_loop_task(self):
        while True:
            for user_id, emote_id in list(self.looping_users.items()):
                try: await self.highrise.send_emote(emote_id, user_id)
                except: 
                    if user_id in self.looping_users: del self.looping_users[user_id]
            await asyncio.sleep(10)

    async def on_tip(self, sender: User, receiver: User, tip: CurrencyItem) -> None:
        if receiver.id == self.bot_id:
            if tip.amount in [500, 1000, 10000]:
                self.data["roles"][sender.id] = "vip"
                self.data["names"][sender.id] = sender.username
                self._save_data()
                await self.highrise.chat(f"💎 @{sender.username} ¡Gracias por el oro! Ahora eres VIP.")

    async def on_chat(self, user: User, message: str) -> None:
        if user.id == self.bot_id: return
        msg = message.strip().lower()
        rol = await self._get_role(user)
        
        # --- TELEPORTS AUTOMÁTICOS ---
        if msg in self.data.get("teleports", {}):
            await self._mover_a(user, msg)
            return

        # --- EMOTES NUMÉRICOS ---
        if msg in EMOTES:
            self.looping_users[user.id] = EMOTES[msg]
            try: await self.highrise.send_emote(EMOTES[msg], user.id)
            except: pass
            return
        if msg == "stop":
            if user.id in self.looping_users: del self.looping_users[user.id]
            return

        if not message.startswith("!"): return
        parts = message.split(); cmd = parts[0].lower(); args = parts[1:]

        try:
            # --- AYUDA ---
            if cmd == "!help":
                cmds = ["✨ SHOW: !apuntarse, !cola, !siguiente", "🛠️ STAFF: !mic, !mute, !kick, !ban, !roles, !bot", 
                        "📍 TP: !listtp, !summ all, !tpme X Y Z", "🎲 JUEGOS: !dado, !raffle, !ship @user", 
                        "💰 ECONOMÍA: !wallet, !tipall [g], !tip5 [g]"]
                for c in cmds: await self.highrise.chat(c); await asyncio.sleep(0.5)

            # --- DUEÑO (OWNER) ---
            if rol == "owner":
                if cmd == "!bot":
                    room = await self.highrise.get_room_users()
                    for u, p in room.content:
                        if u.id == user.id: await self.highrise.teleport(self.bot_id, p)

                elif cmd in ["!summ", "!summon"] and args:
                    room = await self.highrise.get_room_users()
                    my_p = next((p for u, p in room.content if u.id == user.id), None)
                    if my_p:
                        if args[0] == "all":
                            for u, _ in room.content: await self.highrise.teleport(u.id, my_p)
                        else:
                            t = await self._find_user(args[0])
                            if t: await self.highrise.teleport(t.id, my_p)

                elif cmd == "!follow":
                    t = await self._find_user(args[0]) if args else user
                    if t:
                        room = await self.highrise.get_room_users()
                        p = next((p for u, p in room.content if u.id == t.id), None)
                        if p: await self.highrise.walk_to(p)

                elif cmd == "!tipall" and args:
                    room = await self.highrise.get_room_users()
                    for u, _ in room.content:
                        if u.id != self.bot_id: await self.highrise.tip_user(u.id, int(args[0]))

                elif cmd == "!tip5" and args:
                    room = await self.highrise.get_room_users()
                    targets = random.sample([u for u, _ in room.content if u.id != self.bot_id], min(5, len(room.content)-1))
                    for t in targets: await self.highrise.tip_user(t.id, int(args[0]))

                elif cmd in ["!setadmin", "!setpres", "!setvip", "!setjuez"] and args:
                    t = await self._find_user(args[0])
                    if t:
                        self.data["names"][t.id] = t.username
                        if cmd == "!setjuez": self.data["jueces"].append(t.id)
                        else: self.data["roles"][t.id] = cmd[4:]
                        self._save_data(); await self.highrise.chat(f"✅ Rango asignado a @{t.username}")

            # --- STAFF (OWNER, ADMIN, PRESEN) ---
            if rol in ["owner", "admin", "presentador"]:
                if cmd == "!mic" and args:
                    t = await self._find_user(args[0])
                    if t: await self.highrise.add_voice_privilege(t.id)
                elif cmd == "!mute" and args:
                    t = await self._find_user(args[0])
                    if t: await self.highrise.remove_voice_privilege(t.id)
                elif cmd == "!siguiente":
                    await self._pasar_siguiente()
                elif cmd in ["!heart", "!clap", "!wink"]:
                    t = await self._find_user(args[0]) if args else None
                    if t: await self.highrise.react(cmd[1:], t.id)

            # --- PÚBLICO / TODOS ---
            if cmd == "!roles":
                names = self.data.get("names", {})
                for r_type in ["admin", "presentador", "juez", "vip"]:
                    ids = self.data.get("jueces", []) if r_type == "juez" else [k for k, v in self.data["roles"].items() if v == r_type]
                    if ids:
                        txt = f"🔹 {r_type.upper()}: " + ", ".join([f"@{names.get(i, i)}" for i in ids])
                        for chunk in [txt[i:i+140] for i in range(0, len(txt), 140)]: await self.highrise.chat(chunk)

            elif cmd == "!wallet":
                wallet = await self.highrise.get_wallet()
                gold = next((i.amount for i in wallet.content if i.type == "gold"), 0)
                await self.highrise.chat(f"💰 Fondos del bot: {gold}g")

            elif cmd == "!ship" and args:
                await self.highrise.chat(f"❤️ Compatibilidad entre {user.username} y {args[0]}: {random.randint(0,100)}%")

            elif cmd == "!dado":
                await self.highrise.chat(f"🎲 @{user.username} sacó un {random.randint(1,6)}")

        except Exception as e: print(f"Error: {e}")

    async def _pasar_siguiente(self):
        if self.current_performer:
            await self._mover_a(self.current_performer, "publico")
            try: await self.highrise.remove_voice_privilege(self.current_performer.id)
            except: pass
        if self.talent_queue:
            self.current_performer = self.talent_queue.pop(0)
            await self.highrise.chat(f"🎤 ESCENARIO: @{self.current_performer.username}")
            await self._mover_a(self.current_performer, "escenario")
            try: await self.highrise.add_voice_privilege(self.current_performer.id)
            except: pass
        else:
            self.current_performer = None
            await self.highrise.chat("🏁 Cola vacía.")

    async def _mover_a(self, user: User, lugar: str):
        if lugar in self.data.get("teleports", {}):
            d = self.data["teleports"][lugar]
            await self.highrise.teleport(user.id, Position(d["x"], d["y"], d["z"], d["facing"]))

    async def _find_user(self, name: str) -> Optional[User]:
        name = name.replace("@","").lower()
        room = await self.highrise.get_room_users()
        for u, _ in room.content:
            if u.username.lower() == name: return u
        return None