#!/usr/bin/env python3
"""Traduce el nombre de cada ejercicio del inglés al español.

No manda las 130 mil líneas a un traductor genérico: el archivo es grande
porque las indicaciones ya vienen en 10 idiomas. Los nombres son 1.324,
armados con unas 570 palabras de gimnasio. Un traductor general las rompe
(curl → rizo, fly → mosca, bench press → prensa de banco).

Este script usa un glosario. Deja `name` en inglés (lo que ya consumen el
visor y el esquema) y agrega:

    "names": { "en": "barbell bench press", "es": "press de banca con barra" }

Uso:
    python3 scripts/translate_names.py            # revisa, no escribe
    python3 scripts/translate_names.py --apply    # escribe exercises.json y el visor
    python3 scripts/translate_names.py --explain "dumbbell hammer curl"

Para corregir un término, edita WORDS, PHRASES u OVERRIDES y vuelve a correr
con --apply.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "exercises.json"
HTML_PATH = ROOT / "index.html"

STOP = {
    "a", "an", "the", "of", "on", "with", "in", "for", "from", "your", "using",
    "into", "onto", "per", "at", "by", "than", "then", "via", "vs", "versus",
    "each", "every", "just", "onto", "within", "without", "across", "along",
    "around", "during", "between", "through", "up", "out", "off", "over",
}
# "up" / "out" / "off" / "over" solo se descartan si no entraron en una frase.
CONJ = {"and": "y", "&": "y", "to": "a"}


class Piece(NamedTuple):
    kind: str
    es: str
    gender: str = "m"
    modifier: bool = False
    conj: str = ""


def oa(stem: str) -> dict[str, str]:
    return {"m": f"{stem}o", "f": f"{stem}a", "mp": f"{stem}os", "fp": f"{stem}as"}


def inv(singular: str, plural: str) -> dict[str, str]:
    return {"m": singular, "f": singular, "mp": plural, "fp": plural}


AGREE = {
    "sentado": oa("sentad"),
    "inclinado": oa("inclinad"),
    "declinado": oa("declinad"),
    "asistido": oa("asistid"),
    "alterno": oa("altern"),
    "invertido": oa("invertid"),
    "tumbado": oa("tumbad"),
    "colgado": oa("colgad"),
    "concentrado": oa("concentrad"),
    "completo": oa("complet"),
    "medio": oa("medi"),
    "amplio": oa("ampli"),
    "estrecho": oa("estrech"),
    "cerrado": oa("cerrad"),
    "bajo": oa("baj"),
    "alto": oa("alt"),
    "interno": oa("intern"),
    "externo": oa("extern"),
    "negativo": oa("negativ"),
    "profundo": oa("profund"),
    "recto": oa("rect"),
    "plano": oa("plan"),
    "prono": oa("pron"),
    "supino": oa("supin"),
    "rumano": oa("ruman"),
    "ruso": oa("rus"),
    "turco": oa("turc"),
    "corto": oa("cort"),
    "largo": oa("larg"),
    "izquierdo": oa("izquierd"),
    "derecho": oa("derech"),
    "fijo": oa("fij"),
    "elevado": oa("elevad"),
    "modificado": oa("modificad"),
    "lastrado": oa("lastrad"),
    "avanzado": oa("avanzad"),
    "basico": oa("basic"),
    "encogido": oa("encogid"),
    "carpado": oa("carpad"),
    "flexionado": oa("flexionad"),
    "cosaco": oa("cosac"),
    "coreano": oa("corean"),
    "arquero": oa("arquer"),
    "pelvico": oa("pelvic"),
    "bulgaro": {
        "m": "búlgaro", "f": "búlgara", "mp": "búlgaros", "fp": "búlgaras",
    },
    "isometrico": {
        "m": "isométrico", "f": "isométrica", "mp": "isométricos", "fp": "isométricas",
    },
    "basico_acc": {
        "m": "básico", "f": "básica", "mp": "básicos", "fp": "básicas",
    },
    "lateral": inv("lateral", "laterales"),
    "frontal": inv("frontal", "frontales"),
    "posterior": inv("posterior", "posteriores"),
    "superior": inv("superior", "superiores"),
    "inferior": inv("inferior", "inferiores"),
    "horizontal": inv("horizontal", "horizontales"),
    "vertical": inv("vertical", "verticales"),
    "doble": inv("doble", "dobles"),
    "libre": inv("libre", "libres"),
    "hindi": inv("hindú", "hindúes"),
    "unilateral": inv("unilateral", "unilaterales"),
    "neutral": inv("neutro", "neutros"),
    "escapular": inv("escapular", "escapulares"),
    "lumbar": inv("lumbar", "lumbares"),
    "total": inv("total", "totales"),
    "parcial": inv("parcial", "parciales"),
    "diagonal": inv("diagonal", "diagonales"),
    "circular": inv("circular", "circulares"),
}


def M(es: str, gender: str = "m", mod: bool = False) -> Piece:
    return Piece("move", es, gender, mod)


def MU(es: str) -> Piece:
    if es.startswith(("de ", "del ")):
        return Piece("muscle", es)
    return Piece("muscle", f"de {es}")


def ADJ(key: str) -> Piece:
    return Piece("adj", f"@{key}")


def POS(es: str) -> Piece:
    return Piece("pos", es)


def GRIP(es: str) -> Piece:
    return Piece("grip", es if es.startswith("con ") else f"con agarre {es}")


def UNI(es: str) -> Piece:
    return Piece("uni", es)


def STYLE(es: str) -> Piece:
    return Piece("style", es)


def EQUIP(es: str) -> Piece:
    return Piece("equip", es)


def EXTRA(es: str) -> Piece:
    return Piece("extra", es)


def NUM(es: str) -> Piece:
    return Piece("num", es)


WORDS: dict[str, tuple[Piece, ...]] = {}
PHRASES: dict[tuple[str, ...], tuple[Piece, ...]] = {}

def add_phrases(mapping: dict[tuple[str, ...], tuple[Piece, ...]]) -> None:
    PHRASES.update(mapping)


def W(mapping: dict[str, Piece]) -> None:
    for key, piece in mapping.items():
        WORDS[key] = (piece,)


W({
    "curl": M("curl"), "curls": M("curl"),
    "press": M("press"), "presses": M("press"),
    "row": M("remo"), "rows": M("remo"),
    "squat": M("sentadilla", "f"), "squats": M("sentadilla", "f"), "squad": M("sentadilla", "f"),
    "deadlift": M("peso muerto"),
    "raise": M("elevación", "f"), "raises": M("elevación", "f"),
    "extension": M("extensión", "f"), "extensions": M("extensión", "f"),
    "fly": M("aperturas", "fp"), "flyes": M("aperturas", "fp"), "flies": M("aperturas", "fp"),
    "pulldown": M("jalón"), "pulldowns": M("jalón"),
    "pushdown": M("extensión de tríceps", "f"), "pushdowns": M("extensión de tríceps", "f"),
    "crunch": M("crunch"), "crunches": M("crunch"),
    "lunge": M("zancada", "f"), "lunges": M("zancada", "f"),
    "stretch": M("estiramiento"), "stretches": M("estiramiento"), "stretching": M("estiramiento"),
    "twist": M("giro"), "twists": M("giro"),
    "twisting": M("giro", mod=True),
    "shrug": M("encogimiento de hombros"), "shrugs": M("encogimiento de hombros"),
    "plank": M("plancha", "f"),
    "bridge": M("puente"), "bridges": M("puente"),
    "pullover": M("pullover"),
    "kickback": M("patada", "f"), "kickbacks": M("patada", "f"),
    "snatch": M("arranque"),
    "clean": M("cargada", "f"),
    "jerk": M("envión"),
    "thruster": M("thruster"),
    "swing": M("swing", mod=True),
    "burpee": M("burpee"), "burpees": M("burpee"),
    "hyperextension": M("hiperextensión", "f"),
    "abduction": M("abducción", "f"),
    "adduction": M("aducción", "f"),
    "rotation": M("rotación", "f"), "rotational": M("rotación", "f"), "rotate": M("rotación", "f"),
    "circle": M("círculos", "mp"), "circles": M("círculos", "mp"),
    "bend": M("flexión", "f"), "bends": M("flexión", "f"),
    "rollout": M("rodamiento"), "rollerout": M("rodamiento"), "roll": M("rodamiento"),
    "climb": M("escalada", "f"),
    "crawl": M("gateo"),
    "walk": M("caminata", "f"),
    "run": M("carrera", "f"),
    "sprint": M("sprint"), "sprints": M("sprint"),
    "jump": M("salto", mod=True), "jumps": M("salto", mod=True),
    "hop": M("salto", mod=True), "hops": M("salto", mod=True),
    "tap": M("toque", mod=True),
    "touch": M("toque", mod=True), "touchers": M("toques", "mp"),
    "slam": M("slam", mod=True),
    "throw": M("lanzamiento", mod=True),
    "pass": M("pase", mod=True),
    "catch": M("recepción", "f", mod=True),
    "kick": M("patada", "f", mod=True), "kicks": M("patada", "f", mod=True),
    "hook": M("gancho"),
    "flip": M("volteo"),
    "carry": M("acarreo"),
    "drag": M("arrastre"),
    "hold": M("isometría", "f", mod=True),
    "reach": M("alcance", mod=True),
    "tilt": M("inclinación", "f"),
    "step": M("paso"),
    "lift": M("elevación", "f"), "lifting": M("elevación", "f"),
    "thrust": M("empuje"), "thrusts": M("empuje"),
    "pull": M("tirón"),
    "push": M("empuje", mod=True),
    "dip": M("fondos", "mp"), "dips": M("fondos", "mp"),
    "march": M("marcha", "f"),
    "squeeze": M("apretón"),
    "crusher": M("rompecráneos"), "skullcrusher": M("rompecráneos"),
    "climber": M("escalador"), "climbers": M("escalador"),
    "jack": M("salto de tijera"),
    "bicycle": M("bicicleta", "f"),
    "slide": M("deslizamiento"),
    "hinge": M("bisagra", "f"),
    "pulse": M("pulso", mod=True),
    "skip": M("skip"),
    "bounce": M("rebote", mod=True),
    "swing": M("swing", mod=True),
    "bicep": MU("bíceps"), "biceps": MU("bíceps"),
    "tricep": MU("tríceps"), "triceps": MU("tríceps"),
    "chest": MU("pecho"), "pec": MU("pectoral"),
    "shoulder": MU("hombros"), "shoulders": MU("hombros"),
    "delt": MU("deltoides"), "delts": MU("deltoides"), "deltoid": MU("deltoides"),
    "calf": MU("gemelos"), "calves": MU("gemelos"),
    "hamstring": MU("isquiotibiales"), "hamstrings": MU("isquiotibiales"),
    "glute": MU("glúteos"), "glutes": MU("glúteos"), "gluteus": MU("glúteos"),
    "quad": MU("cuádriceps"), "quads": MU("cuádriceps"),
    "lat": MU("dorsales"), "lats": MU("dorsales"),
    "wrist": MU("muñeca"), "wrists": MU("muñecas"),
    "neck": MU("cuello"),
    "hip": MU("cadera"), "hips": MU("cadera"),
    "ab": MU("abdomen"), "abs": MU("abdomen"), "abdominal": MU("abdomen"),
    "oblique": MU("oblicuos"), "obliques": MU("oblicuos"),
    "adductor": MU("aductores"), "adductors": MU("aductores"),
    "abductor": MU("abductores"), "abductors": MU("abductores"),
    "forearm": MU("antebrazo"), "forearms": MU("antebrazos"),
    "piriformis": MU("del piriforme"),
    "tibialis": MU("del tibial"),
    "scapula": MU("escápula"),
    "ankle": MU("tobillo"), "ankles": MU("tobillos"),
    "heel": MU("talón"), "heels": MU("talones"),
    "toe": MU("puntas"), "toes": MU("puntas"),
    "knee": MU("rodilla"), "knees": MU("rodillas"),
    "elbow": MU("codo"), "elbows": MU("codos"),
    "spine": MU("columna"),
    "groin": MU("ingle"),
    "finger": MU("dedos"), "fingers": MU("dedos"),
    "palm": MU("palma"), "palms": MU("palmas"),
    "hand": MU("mano"), "hands": MU("manos"),
    "arm": MU("brazos"), "arms": MU("brazos"),
    "leg": MU("piernas"), "legs": MU("piernas"),
    "head": MU("cabeza"),
    "foot": MU("pie"), "feet": MU("pies"),
    "back": MU("espalda"),
    "trap": MU("trapecio"), "traps": MU("trapecio"),
    "core": MU("core"),
    "femoris": MU("femoral"), "femoral": MU("femoral"),
    "peroneals": MU("peroneos"),
    "dumbbell": EQUIP("con mancuernas"), "dumbbells": EQUIP("con mancuernas"),
    "barbell": EQUIP("con barra"),
    "cable": EQUIP("en polea"), "pulley": EQUIP("en polea"),
    "band": EQUIP("con banda"), "bands": EQUIP("con banda"),
    "kettlebell": EQUIP("con pesa rusa"), "kettlebells": EQUIP("con pesa rusa"),
    "smith": EQUIP("en máquina Smith"),
    "lever": EQUIP("en máquina"),
    "machine": EQUIP("en máquina"),
    "rope": EQUIP("con cuerda"), "ropes": EQUIP("con cuerda"),
    "roller": EQUIP("con rodillo"), "rollerer": EQUIP("con rodillo"),
    "sled": EQUIP("en trineo"),
    "wheel": EQUIP("con rueda abdominal"),
    "towel": EQUIP("con toalla"),
    "bosu": EQUIP("en Bosu"),
    "ring": EQUIP("en anillas"), "rings": EQUIP("en anillas"),
    "bar": EQUIP("con barra"), "bars": EQUIP("con barra"),
    "ball": EQUIP("sobre pelota de ejercicio"),
    "bench": EQUIP("en banco"), "benches": EQUIP("en banco"),
    "floor": EQUIP("en el suelo"), "ground": EQUIP("en el suelo"),
    "wall": EQUIP("en la pared"),
    "box": EQUIP("en cajón"),
    "chair": EQUIP("en silla"),
    "tire": EQUIP("con neumático"),
    "landmine": EQUIP("con landmine"),
    "strap": EQUIP("con correa"), "straps": EQUIP("con correa"),
    "handle": EQUIP("con maneral"), "handles": EQUIP("con maneral"),
    "pad": EQUIP("con almohadilla"),
    "rack": EQUIP("en rack"),
    "cage": EQUIP("en jaula"),
    "platform": EQUIP("en plataforma"),
    "treadmill": EQUIP("en caminadora"),
    "elliptical": EQUIP("en elíptica"),
    "ergometer": EQUIP("en ergómetro"),
    "ez": EQUIP("con barra Z"),
    "stepmill": EQUIP("en escaladora"),
    "stepbox": EQUIP("en cajón"),
    "staircase": EQUIP("en escalera"),
    "bike": EQUIP("en bicicleta"),
    "seated": POS("@sentado"), "sitted": POS("@sentado"),
    "standing": POS("de pie"),
    "lying": POS("@tumbado"),
    "kneeling": POS("de rodillas"),
    "prone": POS("@prono"),
    "supine": POS("@supino"),
    "hanging": POS("@colgado"), "hang": POS("@colgado"),
    "overhead": POS("por encima de la cabeza"),
    "suspended": POS("en suspensión"),
    "squatting": POS("en sentadilla"),
    "incline": ADJ("inclinado"), "inclined": ADJ("inclinado"),
    "decline": ADJ("declinado"),
    "alternate": ADJ("alterno"), "alternating": ADJ("alterno"),
    "assisted": ADJ("asistido"),
    "reverse": ADJ("invertido"), "reversed": ADJ("invertido"), "revers": ADJ("invertido"),
    "negative": ADJ("negativo"),
    "isometric": ADJ("isometrico"),
    "front": ADJ("frontal"),
    "rear": ADJ("posterior"),
    "side": ADJ("lateral"),
    "lateral": ADJ("lateral"),
    "inner": ADJ("interno"),
    "outer": ADJ("externo"),
    "upper": ADJ("superior"),
    "lower": ADJ("inferior"),
    "middle": ADJ("medio"),
    "high": ADJ("alto"),
    "low": ADJ("bajo"),
    "wide": ADJ("amplio"),
    "narrow": ADJ("estrecho"),
    "close": ADJ("cerrado"),
    "full": ADJ("completo"),
    "half": ADJ("medio"),
    "deep": ADJ("profundo"),
    "short": ADJ("corto"),
    "long": ADJ("largo"),
    "left": ADJ("izquierdo"),
    "right": ADJ("derecho"),
    "internal": ADJ("interno"),
    "external": ADJ("externo"),
    "horizontal": ADJ("horizontal"),
    "vertical": ADJ("vertical"),
    "double": ADJ("doble"),
    "romanian": ADJ("rumano"),
    "russian": ADJ("ruso"),
    "turkish": ADJ("turco"),
    "korean": ADJ("coreano"),
    "hindu": ADJ("hindi"),
    "bulgarian": ADJ("bulgaro"),
    "cossack": ADJ("cosaco"),
    "archer": ADJ("arquero"),
    "fixed": ADJ("fijo"),
    "elevated": ADJ("elevado"),
    "modified": ADJ("modificado"),
    "advanced": ADJ("avanzado"),
    "basic": ADJ("basico_acc"),
    "partial": ADJ("parcial"),
    "diagonal": ADJ("diagonal"),
    "circular": ADJ("circular"),
    "scapular": ADJ("escapular"),
    "pelvic": ADJ("pelvico"),
    "flat": ADJ("plano"),
    "bent": ADJ("flexionado"),
    "straight": ADJ("recto"),
    "stiff": ADJ("recto"),
    "tuck": ADJ("encogido"),
    "pike": ADJ("carpado"),
    "concentration": ADJ("concentrado"),
    "free": ADJ("libre"),
    "hammer": STYLE("martillo"),
    "preacher": STYLE("predicador"), "peacher": STYLE("predicador"),
    "spider": STYLE("araña"),
    "arnold": STYLE("Arnold"),
    "zercher": STYLE("Zercher"),
    "jefferson": STYLE("Jefferson"),
    "bradford": STYLE("Bradford"),
    "pallof": STYLE("Pallof"),
    "svend": STYLE("Svend"),
    "zottman": STYLE("Zottman"),
    "pendlay": STYLE("Pendlay"),
    "military": STYLE("militar"),
    "sumo": STYLE("sumo"),
    "hack": STYLE("hack"),
    "goblet": STYLE("goblet"),
    "sissy": STYLE("sissy"),
    "pistol": STYLE("pistol"),
    "donkey": STYLE("donkey"),
    "jm": STYLE("JM"),
    "renegade": STYLE("renegade"),
    "weighted": EQUIP("con lastre"),
    "bodyweight": EQUIP("con peso corporal"),
    "walking": EXTRA("caminando"),
    "plus": EXTRA("plus"),
    "male": EXTRA("hombre"),
    "female": EXTRA("mujer"),
    "pov": EXTRA("vista"),
    "degrees": EXTRA("grados"), "degree": EXTRA("grados"),
    "underhand": GRIP("supino"),
    "overhand": GRIP("prono"),
    "pronated": GRIP("prono"), "pronate": GRIP("prono"),
    "supinated": GRIP("supino"),
    "gripless": EXTRA("sin agarre"),
    "medicine": EQUIP("con balón medicinal"),
    "power": STYLE("de potencia"),
    "speed": STYLE("de velocidad"),
    "forward": EXTRA("hacia adelante"),
    "backward": EXTRA("hacia atrás"), "backwards": EXTRA("hacia atrás"),
    "down": EXTRA("hacia abajo"),
    "upward": EXTRA("hacia arriba"),
    "downward": EXTRA("hacia abajo"),
    "sideways": ADJ("lateral"),
    "apart": EXTRA("separado"),
    "together": EXTRA("juntos"),
    "cross": EXTRA("cruzado"), "crossed": EXTRA("cruzado"),
    "under": EXTRA("por debajo"),
    "above": EXTRA("por encima"),
    "below": EXTRA("por debajo"),
    "behind": EXTRA("por detrás"),
    "inside": EXTRA("por dentro"),
    "outside": EXTRA("por fuera"),
    "against": EXTRA("contra"),
    "support": EXTRA("con apoyo"), "supported": EXTRA("con apoyo"),
    "self": EXTRA("auto"),
    "single": EXTRA("unilateral"),
    "unilateral": EXTRA("unilateral"),
    "balance": EXTRA("de equilibrio"),
    "dynamic": EXTRA("dinámico"),
    "static": EXTRA("estático"),
    "explosive": EXTRA("explosivo"),
    "pause": EXTRA("con pausa"), "paused": EXTRA("con pausa"),
    "slow": EXTRA("lento"),
    "fast": EXTRA("rápido"),
    "body": EXTRA("cuerpo"),
    "weight": EQUIP("con peso"),
    "stability": EXTRA("de estabilidad"),
    "exercise": EXTRA(""),
    "grip": EXTRA(""),
    "range": EXTRA("rango"),
    "motion": EXTRA("de movimiento"),
    "major": EXTRA("mayor"),
    "minor": EXTRA("menor"),
    "rectus": EXTRA("recto"),
    "slinger": M("balanceo de brazos"), "slingers": M("balanceo de brazos"),
    "battle": EXTRA("de batalla"), "battling": EXTRA("de batalla"),
    "foam": EQUIP("con rodillo"),
    "plate": EQUIP("con disco"), "plates": EQUIP("con disco"),
    "chain": EQUIP("con cadena"),
    "sandbag": EQUIP("con saco"),
    "abwheel": EQUIP("con rueda abdominal"),
    "trx": EQUIP("en suspensión"),
    "suspension": POS("en suspensión"),
    "parallettes": EQUIP("en paralelas bajas"),
    "mat": EQUIP("en colchoneta"),
    "yoga": EXTRA("de yoga"),
    "pilates": EXTRA("de pilates"),
    "cardio": EXTRA("de cardio"),
    "hiit": EXTRA("HIIT"),
    "tabata": EXTRA("Tabata"),
    "amrap": EXTRA("AMRAP"),
    "emom": EXTRA("EMOM"),
    "reps": EXTRA("repeticiones"),
    "rep": EXTRA("repetición"),
    "set": EXTRA("serie"),
    "sets": EXTRA("series"),
    "min": EXTRA("min"),
    "sec": EXTRA("s"),
    "kg": EXTRA("kg"),
    "lb": EXTRA("lb"),
    "lbs": EXTRA("lb"),
})

add_phrases({
    ("bench", "press"): (M("press de banca"),),
    ("leg", "curl"): (M("curl femoral"),),
    ("leg", "extension"): (M("extensión de cuádriceps", "f"),),
    ("leg", "press"): (M("prensa de piernas", "f"),),
    ("calf", "press"): (M("prensa de gemelos", "f"),),
    ("lat", "pulldown"): (M("jalón al pecho"),),
    ("face", "pull"): (M("jalón a la cara"),),
    ("upright", "row"): (M("remo al mentón"),),
    ("good", "morning"): (M("buenos días"),),
    ("skull", "crusher"): (M("rompecráneos"),),
    ("mountain", "climber"): (M("escalador"),),
    ("mountain", "climbers"): (M("escalador"),),
    ("jumping", "jack"): (M("saltos de tijera", "mp"),),
    ("jumping", "jacks"): (M("saltos de tijera", "mp"),),
    ("box", "jump"): (M("salto al cajón"),),
    ("star", "jump"): (M("salto estrella"),),
    ("push", "up"): (M("flexión", "f"),),
    ("push", "ups"): (M("flexiones", "fp"),),
    ("pull", "up"): (M("dominada", "f"),),
    ("pull", "ups"): (M("dominadas", "fp"),),
    ("chin", "up"): (M("dominada supina", "f"),),
    ("chin", "ups"): (M("dominadas supinas", "fp"),),
    ("sit", "up"): (M("abdominal"),),
    ("sit", "ups"): (M("abdominales", "mp"),),
    ("muscle", "up"): (M("muscle-up"),),
    ("step", "up"): (M("subida al cajón", "f"),),
    ("get", "up"): (M("levantamiento"),),
    ("v", "up"): (M("V-up"),),
    ("l", "sit"): (M("L-sit"),),
    ("y", "raise"): (M("elevación en Y", "f"),),
    ("t", "raise"): (M("elevación en T", "f"),),
    ("w", "press"): (M("press en W"),),
    ("pull", "through"): (M("pase entre las piernas"),),
    ("pull", "apart"): (M("aperturas", "fp"),),
    ("drag", "curl"): (M("curl de arrastre"),),
    ("around", "the", "world"): (M("vuelta al mundo", "f"),),
    ("world", "greatest", "stretch"): (M("el gran estiramiento"),),
    ("farmer", "walk"): (M("paseo del granjero"),),
    ("farmers", "walk"): (M("paseo del granjero"),),
    ("farmer", "carry"): (M("paseo del granjero"),),
    ("farmers", "carry"): (M("paseo del granjero"),),
    ("air", "bike"): (M("bicicleta en el aire", "f"),),
    ("curl", "up"): (M("curl-up"),),
    ("pull", "in"): (M("encogimiento de piernas"),),
    ("body", "up"): (M("body-up"),),
    ("dip", "pull", "up"): (M("fondo a dominada"),),
    ("l", "pull", "up"): (M("dominada en L", "f"),),
    ("pike", "to", "cobra"): (M("de pike a cobra"),),
    ("elbow", "to", "knee"): (M("codo a rodilla"),),
    ("close", "grip"): (GRIP("cerrado"),),
    ("wide", "grip"): (GRIP("abierto"),),
    ("reverse", "grip"): (GRIP("invertido"),),
    ("neutral", "grip"): (GRIP("neutro"),),
    ("narrow", "grip"): (GRIP("estrecho"),),
    ("mixed", "grip"): (GRIP("mixto"),),
    ("shoulder", "grip"): (GRIP("al hombro"),),
    ("clean", "grip"): (GRIP("de cargada"),),
    ("pronate", "grip"): (GRIP("prono"),),
    ("parallel", "grip"): (GRIP("paralelo"),),
    ("false", "grip"): (GRIP("falso"),),
    ("one", "arm"): (UNI("a un brazo"),),
    ("single", "arm"): (UNI("a un brazo"),),
    ("one", "leg"): (UNI("a una pierna"),),
    ("single", "leg"): (UNI("a una pierna"),),
    ("one", "hand"): (UNI("a una mano"),),
    ("two", "arm"): (UNI("a dos brazos"),),
    ("two", "arms"): (UNI("a dos brazos"),),
    ("two", "legs"): (UNI("a dos piernas"),),
    ("both", "legs"): (UNI("a dos piernas"),),
    ("both", "arms"): (UNI("a dos brazos"),),
    ("behind", "neck"): (POS("tras nuca"),),
    ("behind", "the", "neck"): (POS("tras nuca"),),
    ("behind", "head"): (POS("tras nuca"),),
    ("behind", "the", "head"): (POS("tras nuca"),),
    ("exercise", "ball"): (EQUIP("sobre pelota de ejercicio"),),
    ("stability", "ball"): (EQUIP("sobre pelota de ejercicio"),),
    ("medicine", "ball"): (EQUIP("con balón medicinal"),),
    ("bosu", "ball"): (EQUIP("en Bosu"),),
    ("swiss", "ball"): (EQUIP("sobre pelota de ejercicio"),),
    ("smith", "machine"): (EQUIP("en máquina Smith"),),
    ("ez", "bar"): (EQUIP("con barra Z"),),
    ("ez", "barbell"): (EQUIP("con barra Z"),),
    ("trap", "bar"): (EQUIP("con barra hexagonal"),),
    ("v", "bar"): (EQUIP("con barra en V"),),
    ("t", "bar"): (EQUIP("con barra T"),),
    ("sz", "bar"): (EQUIP("con barra SZ"),),
    ("olympic", "barbell"): (EQUIP("con barra olímpica"),),
    ("resistance", "band"): (EQUIP("con banda"),),
    ("body", "weight"): (EQUIP("con peso corporal"),),
    ("battling", "ropes"): (EQUIP("con cuerdas de batalla"),),
    ("battle", "rope"): (EQUIP("con cuerdas de batalla"),),
    ("battle", "ropes"): (EQUIP("con cuerdas de batalla"),),
    ("flat", "bench"): (EQUIP("en banco plano"),),
    ("parallel", "bars"): (EQUIP("en paralelas"),),
    ("arm", "blaster"): (EQUIP("con arm blaster"),),
    ("dip", "cage"): (EQUIP("en estación de fondos"),),
    ("bent", "over"): (POS("con torso inclinado"),),
    ("bent", "arm"): (EXTRA("con brazos flexionados"),),
    ("bent", "arms"): (EXTRA("con brazos flexionados"),),
    ("bent", "knee"): (EXTRA("con rodillas flexionadas"),),
    ("bent", "knees"): (EXTRA("con rodillas flexionadas"),),
    ("straight", "leg"): (EXTRA("con piernas rectas"),),
    ("straight", "legs"): (EXTRA("con piernas rectas"),),
    ("straight", "arm"): (EXTRA("con brazos rectos"),),
    ("straight", "arms"): (EXTRA("con brazos rectos"),),
    ("straight", "back"): (EXTRA("con espalda recta"),),
    ("stiff", "leg"): (EXTRA("con piernas rígidas"),),
    ("stiff", "legs"): (EXTRA("con piernas rígidas"),),
    ("arms", "overhead"): (EXTRA("con los brazos por encima de la cabeza"),),
    ("arm", "overhead"): (EXTRA("con los brazos por encima de la cabeza"),),
    ("high", "bar"): (EXTRA("con barra alta"),),
    ("low", "bar"): (EXTRA("con barra baja"),),
    ("all", "fours"): (POS("en cuadrupedia"),),
    ("back", "and", "forth"): (EXTRA("adelante y atrás"),),
    ("side", "to", "side"): (EXTRA("de lado a lado"),),
    ("up", "and", "down"): (EXTRA("arriba y abajo"),),
    ("palms", "up"): (GRIP("con palmas hacia arriba"),),
    ("palms", "down"): (GRIP("con palmas hacia abajo"),),
    ("palm", "in"): (GRIP("con palmas hacia adentro"),),
    ("bottoms", "up"): (STYLE("bottoms-up"),),
    ("glute", "ham"): (STYLE("glute-ham"),),
    ("two", "one"): (EXTRA("dos a uno"),),
    ("off", "dumbbell"): (EQUIP("sobre mancuernas"),),
    ("off", "dumbbells"): (EQUIP("sobre mancuernas"),),
    ("against", "wall"): (POS("contra la pared"),),
    ("against", "the", "wall"): (POS("contra la pared"),),
    ("range", "of", "motion"): (EXTRA("rango completo de movimiento"),),
    ("full", "range"): (EXTRA("rango completo"),),
    ("back", "pov"): (EXTRA("vista posterior"),),
    ("side", "pov"): (EXTRA("vista lateral"),),
    ("front", "pov"): (EXTRA("vista frontal"),),
    ("throw", "down"): (M("lanzamiento hacia abajo", mod=True),),
    ("upper", "back"): (MU("espalda alta"),),
    ("lower", "back"): (MU("espalda baja"),),
    ("rear", "delt"): (MU("deltoides posterior"),),
    ("front", "delt"): (MU("deltoides frontal"),),
    ("side", "delt"): (MU("deltoides lateral"),),
    ("rectus", "femoris"): (MU("del recto femoral"),),
    ("pectoralis", "major"): (MU("del pectoral mayor"),),
    ("high", "pulley"): (EQUIP("en polea alta"),),
    ("low", "pulley"): (EQUIP("en polea baja"),),
    ("jump", "squat"): (M("sentadilla con salto", "f"),),
    ("squat", "jump"): (M("sentadilla con salto", "f"),),
    ("split", "squat"): (M("sentadilla dividida", "f"),),
    ("front", "squat"): (M("sentadilla frontal", "f"),),
    ("overhead", "squat"): (M("sentadilla overhead", "f"),),
    ("hack", "squat"): (M("sentadilla hack", "f"),),
    ("goblet", "squat"): (M("sentadilla goblet", "f"),),
    ("pistol", "squat"): (M("sentadilla pistol", "f"),),
    ("sissy", "squat"): (M("sentadilla sissy", "f"),),
    ("cossack", "squat"): (M("sentadilla cosaca", "f"),),
    ("cossack", "squats"): (M("sentadilla cosaca", "f"),),
    ("sumo", "squat"): (M("sentadilla sumo", "f"),),
    ("sumo", "deadlift"): (M("peso muerto sumo"),),
    ("romanian", "deadlift"): (M("peso muerto rumano"),),
    ("power", "clean"): (M("cargada de potencia", "f"),),
    ("hang", "clean"): (M("cargada de potencia colgante", "f"),),
    ("muscle", "up"): (M("muscle-up"),),
    ("handstand"): (M("parada de manos", "f"),),
    ("hand", "stand"): (M("parada de manos", "f"),),
    ("push", "press"): (M("push press"),),
    ("face", "pull"): (M("jalón a la cara"),),
    ("hip", "thrust"): (M("empuje de cadera"),),
    ("hip", "thrusts"): (M("empuje de cadera"),),
    ("glute", "bridge"): (M("puente de glúteos"),),
    ("russian", "twist"): (M("giro ruso"),),
    ("hammer", "curl"): (M("curl martillo"),),
    ("preacher", "curl"): (M("curl predicador"),),
    ("concentration", "curl"): (M("curl concentrado"),),
    ("spider", "curl"): (M("curl araña"),),
    ("reverse", "curl"): (M("curl invertido"),),
    ("drag", "curl"): (M("curl de arrastre"),),
    ("wrist", "curl"): (M("curl de muñeca"),),
    ("reverse", "fly"): (M("aperturas invertidas", "fp"),),
    ("lateral", "raise"): (M("elevación lateral", "f"),),
    ("front", "raise"): (M("elevación frontal", "f"),),
    ("rear", "delt", "fly"): (M("aperturas posteriores", "fp"),),
    ("rear", "delt", "raise"): (M("elevación posterior", "f"),),
    ("calf", "raise"): (M("elevación de gemelos", "f"),),
    ("leg", "raise"): (M("elevación de piernas", "f"),),
    ("knee", "raise"): (M("elevación de rodillas", "f"),),
    ("side", "bend"): (M("flexión lateral", "f"),),
    ("side", "plank"): (M("plancha lateral", "f"),),
    ("front", "plank"): (M("plancha frontal", "f"),),
    ("back", "extension"): (M("extensión de espalda", "f"),),
    ("hip", "extension"): (M("extensión de cadera", "f"),),
    ("hip", "abduction"): (M("abducción de cadera", "f"),),
    ("hip", "adduction"): (M("aducción de cadera", "f"),),
    ("leg", "curl"): (M("curl femoral"),),
    ("leg", "extension"): (M("extensión de cuádriceps", "f"),),
    ("leg", "press"): (M("prensa de piernas", "f"),),
    ("shoulder", "press"): (M("press de hombros"),),
    ("chest", "press"): (M("press de pecho"),),
    ("military", "press"): (M("press militar"),),
    ("arnold", "press"): (M("press Arnold"),),
    ("bench", "press"): (M("press de banca"),),
    ("floor", "press"): (M("press en el suelo"),),
    ("close", "grip", "bench", "press"): (M("press de banca"), GRIP("cerrado")),
    ("wide", "grip", "bench", "press"): (M("press de banca"), GRIP("abierto")),
    ("incline", "bench", "press"): (M("press de banca"), ADJ("inclinado")),
    ("decline", "bench", "press"): (M("press de banca"), ADJ("declinado")),
    ("one", "arm", "row"): (M("remo"), UNI("a un brazo")),
    ("single", "arm", "row"): (M("remo"), UNI("a un brazo")),
    ("bent", "over", "row"): (M("remo"), POS("con torso inclinado")),
    ("upright", "row"): (M("remo al mentón"),),
    ("lat", "pulldown"): (M("jalón al pecho"),),
    ("face", "pull"): (M("jalón a la cara"),),
    ("good", "morning"): (M("buenos días"),),
    ("skull", "crusher"): (M("rompecráneos"),),
    ("push", "up"): (M("flexión", "f"),),
    ("pull", "up"): (M("dominada", "f"),),
    ("chin", "up"): (M("dominada supina", "f"),),
    ("sit", "up"): (M("abdominal"),),
    ("muscle", "up"): (M("muscle-up"),),
    ("deadlift",): (M("peso muerto"),),
    ("romanian", "deadlift"): (M("peso muerto rumano"),),
    ("sumo", "deadlift"): (M("peso muerto sumo"),),
    ("stiff", "leg", "deadlift"): (M("peso muerto"), EXTRA("con piernas rígidas")),
    ("straight", "leg", "deadlift"): (M("peso muerto"), EXTRA("con piernas rectas")),
    ("single", "leg", "deadlift"): (M("peso muerto"), UNI("a una pierna")),
    ("one", "leg", "deadlift"): (M("peso muerto"), UNI("a una pierna")),
    ("calf", "raise"): (M("elevación de gemelos", "f"),),
    ("donkey", "calf", "raise"): (M("elevación de gemelos", "f"), STYLE("donkey")),
    ("seated", "calf", "raise"): (M("elevación de gemelos", "f"), POS("@sentado")),
    ("standing", "calf", "raise"): (M("elevación de gemelos", "f"), POS("de pie")),
    ("leg", "curl"): (M("curl femoral"),),
    ("lying", "leg", "curl"): (M("curl femoral"), POS("@tumbado")),
    ("seated", "leg", "curl"): (M("curl femoral"), POS("@sentado")),
    ("one", "leg", "curl"): (M("curl femoral"), UNI("a una pierna")),
    ("single", "leg", "curl"): (M("curl femoral"), UNI("a una pierna")),
    ("leg", "extension"): (M("extensión de cuádriceps", "f"),),
    ("leg", "press"): (M("prensa de piernas", "f"),),
    ("one", "leg", "press"): (M("prensa de piernas", "f"), UNI("a una pierna")),
    ("single", "leg", "press"): (M("prensa de piernas", "f"), UNI("a una pierna")),
    ("hack", "squat"): (M("sentadilla hack", "f"),),
    ("goblet", "squat"): (M("sentadilla goblet", "f"),),
    ("front", "squat"): (M("sentadilla frontal", "f"),),
    ("overhead", "squat"): (M("sentadilla overhead", "f"),),
    ("pistol", "squat"): (M("sentadilla pistol", "f"),),
    ("sissy", "squat"): (M("sentadilla sissy", "f"),),
    ("split", "squat"): (M("sentadilla dividida", "f"),),
    ("jump", "squat"): (M("sentadilla con salto", "f"),),
    ("squat", "jump"): (M("sentadilla con salto", "f"),),
    ("box", "jump"): (M("salto al cajón"),),
    ("hip", "thrust"): (M("empuje de cadera"),),
    ("glute", "bridge"): (M("puente de glúteos"),),
    ("russian", "twist"): (M("giro ruso"),),
    ("mountain", "climber"): (M("escalador"),),
    ("jumping", "jack"): (M("saltos de tijera", "mp"),),
    ("face", "pull"): (M("jalón a la cara"),),
    ("upright", "row"): (M("remo al mentón"),),
    ("good", "morning"): (M("buenos días"),),
    ("skull", "crusher"): (M("rompecráneos"),),
    ("lat", "pulldown"): (M("jalón al pecho"),),
    ("bench", "press"): (M("press de banca"),),
    ("shoulder", "press"): (M("press de hombros"),),
    ("military", "press"): (M("press militar"),),
    ("chest", "press"): (M("press de pecho"),),
    ("hammer", "curl"): (M("curl martillo"),),
    ("preacher", "curl"): (M("curl predicador"),),
    ("bicep", "curl"): (M("curl de bíceps"),),
    ("biceps", "curl"): (M("curl de bíceps"),),
    ("tricep", "extension"): (M("extensión de tríceps", "f"),),
    ("triceps", "extension"): (M("extensión de tríceps", "f"),),
    ("tricep", "pushdown"): (M("extensión de tríceps", "f"),),
    ("triceps", "pushdown"): (M("extensión de tríceps", "f"),),
    ("lateral", "raise"): (M("elevación lateral", "f"),),
    ("front", "raise"): (M("elevación frontal", "f"),),
    ("side", "bend"): (M("flexión lateral", "f"),),
    ("side", "plank"): (M("plancha lateral", "f"),),
    ("pull", "up"): (M("dominada", "f"),),
    ("push", "up"): (M("flexión", "f"),),
    ("chin", "up"): (M("dominada supina", "f"),),
    ("sit", "up"): (M("abdominal"),),
    ("calf", "raise"): (M("elevación de gemelos", "f"),),
    ("wrist", "curl"): (M("curl de muñeca"),),
    ("reverse", "curl"): (M("curl invertido"),),
    ("reverse", "fly"): (M("aperturas invertidas", "fp"),),
    ("concentration", "curl"): (M("curl concentrado"),),
    ("farmer", "walk"): (M("paseo del granjero"),),
    ("step", "up"): (M("subida al cajón", "f"),),
    ("muscle", "up"): (M("muscle-up"),),
    ("get", "up"): (M("levantamiento"),),
    ("air", "bike"): (M("bicicleta en el aire", "f"),),
    ("all", "fours"): (POS("en cuadrupedia"),),
    ("one", "arm"): (UNI("a un brazo"),),
    ("single", "arm"): (UNI("a un brazo"),),
    ("one", "leg"): (UNI("a una pierna"),),
    ("single", "leg"): (UNI("a una pierna"),),
    ("close", "grip"): (GRIP("cerrado"),),
    ("wide", "grip"): (GRIP("abierto"),),
    ("reverse", "grip"): (GRIP("invertido"),),
    ("neutral", "grip"): (GRIP("neutro"),),
    ("narrow", "grip"): (GRIP("estrecho"),),
    ("exercise", "ball"): (EQUIP("sobre pelota de ejercicio"),),
    ("stability", "ball"): (EQUIP("sobre pelota de ejercicio"),),
    ("medicine", "ball"): (EQUIP("con balón medicinal"),),
    ("smith", "machine"): (EQUIP("en máquina Smith"),),
    ("ez", "barbell"): (EQUIP("con barra Z"),),
    ("ez", "bar"): (EQUIP("con barra Z"),),
    ("body", "weight"): (EQUIP("con peso corporal"),),
    ("bent", "over"): (POS("con torso inclinado"),),
    ("behind", "the", "neck"): (POS("tras nuca"),),
    ("behind", "neck"): (POS("tras nuca"),),
    ("behind", "head"): (POS("tras nuca"),),
    ("high", "bar"): (EXTRA("con barra alta"),),
    ("low", "bar"): (EXTRA("con barra baja"),),
    ("parallel", "bars"): (EQUIP("en paralelas"),),
    ("flat", "bench"): (EQUIP("en banco plano"),),
    ("v", "bar"): (EQUIP("con barra en V"),),
    ("t", "bar"): (EQUIP("con barra T"),),
    ("trap", "bar"): (EQUIP("con barra hexagonal"),),
    ("stiff", "leg"): (EXTRA("con piernas rígidas"),),
    ("straight", "leg"): (EXTRA("con piernas rectas"),),
    ("straight", "legs"): (EXTRA("con piernas rectas"),),
    ("bent", "knee"): (EXTRA("con rodillas flexionadas"),),
    ("bent", "knees"): (EXTRA("con rodillas flexionadas"),),
    ("arms", "overhead"): (EXTRA("con los brazos por encima de la cabeza"),),
    ("throw", "down"): (M("lanzamiento hacia abajo", mod=True),),
    ("pull", "through"): (M("pase entre las piernas"),),
    ("around", "the", "world"): (M("vuelta al mundo", "f"),),
    ("jumping", "jack"): (M("saltos de tijera", "mp"),),
    ("box", "jump"): (M("salto al cajón"),),
    ("power", "clean"): (M("cargada de potencia", "f"),),
    ("face", "pull"): (M("jalón a la cara"),),
    ("good", "morning"): (M("buenos días"),),
    ("skull", "crusher"): (M("rompecráneos"),),
    ("upright", "row"): (M("remo al mentón"),),
    ("lat", "pulldown"): (M("jalón al pecho"),),
    ("leg", "press"): (M("prensa de piernas", "f"),),
    ("leg", "curl"): (M("curl femoral"),),
    ("leg", "extension"): (M("extensión de cuádriceps", "f"),),
    ("calf", "raise"): (M("elevación de gemelos", "f"),),
    ("bench", "press"): (M("press de banca"),),
})


def _expand_overlapping_unis() -> None:
    additions: dict[tuple[str, ...], tuple[Piece, ...]] = {}
    unis = [
        (key, pieces)
        for key, pieces in PHRASES.items()
        if any(p.kind == "uni" for p in pieces) and not any(p.kind == "move" for p in pieces)
    ]
    moves = [
        (key, pieces)
        for key, pieces in PHRASES.items()
        if key and any(p.kind == "move" for p in pieces)
    ]
    for uni_key, uni_pieces in unis:
        if not uni_key:
            continue
        for move_key, move_pieces in moves:
            if move_key[0] != uni_key[-1]:
                continue
            combined = uni_key[:-1] + move_key
            if combined in PHRASES or combined in additions:
                continue
            additions[combined] = uni_pieces + move_pieces
    PHRASES.update(additions)


_expand_overlapping_unis()

# Nombres completos que el glosario no deja naturales.
OVERRIDES: dict[str, str] = {}

EXPECT = {
    "barbell bench press": "press de banca con barra",
    "dumbbell curl": "curl con mancuernas",
    "dumbbell hammer curl": "curl martillo con mancuernas",
    "dumbbell seated one arm bicep curl": "curl de bíceps a un brazo sentado con mancuerna",
    "barbell romanian deadlift": "peso muerto rumano con barra",
    "barbell squat": "sentadilla con barra",
    "pull-up": "dominada",
    "push-up": "flexión",
    "chin-up": "dominada supina",
    "cable lat pulldown": "jalón al pecho en polea",
    "lever seated row": "remo sentado en máquina",
    "smith bench press": "press de banca en máquina Smith",
    "incline dumbbell fly": "aperturas inclinadas con mancuernas",
    "assisted pull-up": "dominada asistida",
    "lying leg curl": "curl femoral tumbado",
    "barbell bent over row": "remo con torso inclinado con barra",
    "close-grip bench press": "press de banca con agarre cerrado",
    "kettlebell swing": "swing con pesa rusa",
    "russian twist": "giro ruso",
    "mountain climber": "escalador",
    "hip thrust": "empuje de cadera",
    "glute bridge": "puente de glúteos",
    "face pull": "jalón a la cara",
    "upright row": "remo al mentón",
    "lateral raise": "elevación lateral",
    "triceps dip": "fondos de tríceps",
    "cable pushdown": "extensión de tríceps en polea",
    "good morning": "buenos días",
    "deadlift": "peso muerto",
    "plank": "plancha",
    "burpee": "burpee",
    "calf raise": "elevación de gemelos",
    "leg press": "prensa de piernas",
    "shoulder press": "press de hombros",
    "barbell incline bench press": "press de banca inclinado con barra",
    "3/4 sit-up": "abdominal 3/4",
    "45° side bend": "flexión lateral a 45°",
    "sit-up v. 2": "abdominal v. 2",
    "push-up (male)": "flexión (hombre)",
}


W({
    "angle": EXTRA("en ángulo"),
    "angled": EXTRA("en ángulo"),
    "anti": EXTRA("anti"),
    "astride": EXTRA("a horcajadas"),
    "attachment": EXTRA("con accesorio"),
    "bear": STYLE("de oso"),
    "big": EXTRA("grande"),
    "board": EQUIP("en tabla de equilibrio"),
    "bowling": EXTRA("tipo bowling"),
    "boxing": EXTRA("de boxeo"),
    "breeding": STYLE("breeding"),
    "bug": EXTRA("bicho"),
    "butt": MU("glúteos"),
    "butterfly": STYLE("mariposa"),
    "cambered": STYLE("curva"),
    "can": EXTRA("full can"),
    "captains": EXTRA("de capitán"),
    "caster": EXTRA("caster"),
    "cat": EXTRA("gato"),
    "chin": M("dominada supina", "f"),
    "clap": EXTRA("con palmada"),
    "clasped": EXTRA("con manos entrelazadas"),
    "clock": EXTRA("de reloj"),
    "closer": ADJ("cerrado"),
    "cocoons": M("capullos", "mp"),
    "contralateral": EXTRA("contralateral"),
    "crab": STYLE("cangrejo"),
    "crossover": M("cruce de poleas"),
    "crossovers": M("cruces de polea", "mp"),
    "cuban": STYLE("cubano"),
    "curtsey": STYLE("de reverencia"),
    "cycle": EQUIP("en bicicleta"),
    "dead": EXTRA("muerto"),
    "depresor": EXTRA("depresor"),
    "depth": EXTRA("en profundidad"),
    "diamond": GRIP("de diamante"),
    "dog": EXTRA("perro"),
    "drive": M("empuje"),
    "drop": EXTRA("con caída"),
    "elevator": M("elevador"),
    "equipment": EXTRA("con equipo"),
    "extended": EXTRA("extendido"),
    "face": EXTRA("a la cara"),
    "facing": EXTRA("mirando hacia arriba"),
    "fallout": M("caída abdominal", "f"),
    "figure": EXTRA("en figura"),
    "flag": M("bandera", "f"),
    "flexion": M("flexión", "f"),
    "flexor": EXTRA("flexor"),
    "flutter": STYLE("de aleteo"),
    "frankenstein": STYLE("Frankenstein"),
    "french": STYLE("francés"),
    "frog": STYLE("rana"),
    "gironda": STYLE("Gironda"),
    "gorilla": STYLE("gorila"),
    "gravity": EXTRA("antigravedad"),
    "gripper": EQUIP("con pinza"),
    "guillotine": STYLE("guillotina"),
    "handstand": M("parada de manos", "f"),
    "hug": M("abrazo"),
    "hyght": STYLE("Hyght"),
    "hyper": M("hiperextensión", "f"),
    "impossible": STYLE("imposible"),
    "inchworm": M("oruga", "f"),
    "intermediate": EXTRA("intermedio"),
    "inverse": ADJ("invertido"),
    "inverted": ADJ("invertido"),
    "iron": STYLE("de hierro"),
    "jackknife": M("navaja", "f"),
    "janda": STYLE("Janda"),
    "judo": STYLE("de judo"),
    "kayak": STYLE("kayak"),
    "keens": MU("rodillas"),
    "kipping": STYLE("con kipping"),
    "knife": EXTRA("navaja"),
    "lean": EXTRA("inclinado"),
    "legged": EXTRA("pierna"),
    "london": STYLE("de Londres"),
    "maltese": M("maltesa", "f"),
    "monster": STYLE("del monstruo"),
    "multiple": EXTRA("múltiple"),
    "neutral": GRIP("neutro"),
    "otis": STYLE("Otis"),
    "outstretched": EXTRA("extendida"),
    "parallel": GRIP("paralelo"),
    "pin": EXTRA("con pines"),
    "pirate": STYLE("pirata"),
    "planche": M("planche", "f"),
    "plyo": STYLE("pliométrico"),
    "point": EXTRA("puntos"),
    "pose": EXTRA("postura"),
    "position": EXTRA(""),
    "posterior": ADJ("posterior"),
    "potty": STYLE("profunda"),
    "prisoner": STYLE("prisionero"),
    "pro": EXTRA("pro"),
    "pronation": M("pronación", "f"),
    "pyramid": STYLE("pirámide"),
    "quarter": EXTRA("de un cuarto"),
    "quick": EXTRA("rápido"),
    "raised": ADJ("elevado"),
    "reclining": POS("@tumbado"),
    "release": EXTRA("con soltura"),
    "response": EXTRA("de reacción"),
    "retractor": EXTRA("retractor"),
    "rocking": EXTRA("con balanceo"),
    "rocky": STYLE("Rocky"),
    "rotary": EXTRA("rotatorio"),
    "round": EXTRA("circular"),
    "runners": STYLE("del corredor"),
    "saw": M("sierra", "f"),
    "scissor": STYLE("de tijera"),
    "scott": STYLE("Scott"),
    "seesaw": STYLE("balancín"),
    "semi": EXTRA("semi"),
    "sequence": EXTRA("en secuencia"),
    "sit": POS("@sentado"),
    "skater": STYLE("de patinador"),
    "ski": STYLE("de esquí"),
    "skier": M("paso de esquí"),
    "skin": EXTRA("piel"),
    "skull": EXTRA("al cráneo"),
    "sledge": EQUIP("con mazo"),
    "spell": EXTRA("hechizo"),
    "sphinx": M("esfinge", "f"),
    "split": EXTRA("dividida"),
    "stabilization": EXTRA("de estabilización"),
    "stalder": STYLE("Stalder"),
    "stance": EXTRA("en postura"),
    "stationary": EXTRA("estática"),
    "sternum": MU("esternón"),
    "stirrups": EQUIP("con estribos"),
    "stork": STYLE("de cigüeña"),
    "straddle": EXTRA("a horcajadas"),
    "stride": EXTRA("de zancada"),
    "style": EXTRA(""),
    "superman": STYLE("Superman"),
    "supination": M("supinación", "f"),
    "supper": EXTRA("cruzadas"),
    "swimmer": STYLE("de nadador"),
    "tate": STYLE("Tate"),
    "tennis": EQUIP("con pelota de tenis"),
    "thibaudeau": STYLE("Thibaudeau"),
    "three": EXTRA("triple"),
    "trainer": EQUIP("en elíptica"),
    "twin": EXTRA("doble"),
    "twisted": EXTRA("con torsión"),
    "two": EXTRA("dos"),
    "upright": ADJ("vertical"),
    "ups": M("elevaciones", "fp"),
    "v": EXTRA("en V"),
    "variation": EXTRA("variación"),
    "waiter": STYLE("de camarero"),
    "wind": EXTRA(""),
    "windmill": M("molino"),
    "wipers": M("limpiaparabrisas", "mp"),
    "world": EXTRA("al mundo"),
    "one": EXTRA("uno"),
})

add_phrases({
    ("dead", "bug"): (M("bicho muerto"),),
    ("front", "lever"): (M("front lever"),),
    ("back", "lever"): (M("back lever"),),
    ("front", "lever", "reps"): (M("front lever"),),
    ("cross", "body"): (EXTRA("cruzado al cuerpo"),),
    ("lower", "body"): (MU("tren inferior"),),
    ("upper", "body"): (MU("tren superior"),),
    ("planche", "push", "up"): (M("flexión en planche", "f"),),
    ("bear", "crawl"): (M("gateo de oso"),),
    ("butt", "ups"): (M("elevación de glúteos", "f"),),
    ("skin", "the", "cat"): (M("skin the cat"),),
    ("spell", "caster"): (M("spell caster"),),
    ("upward", "facing", "dog"): (M("perro boca arriba"),),
    ("butterfly", "yoga", "pose"): (M("postura de la mariposa", "f"),),
    ("london", "bridge"): (M("puente de Londres"),),
    ("monster", "walk"): (M("caminata del monstruo", "f"),),
    ("inchworm",): (M("oruga", "f"),),
    ("flutter", "kicks"): (M("patadas de aleteo", "fp"),),
    ("runners", "stretch"): (M("estiramiento del corredor"),),
    ("curtsey", "squat"): (M("sentadilla de reverencia", "f"),),
    ("frankenstein", "squat"): (M("sentadilla Frankenstein", "f"),),
    ("potty", "squat"): (M("sentadilla profunda", "f"),),
    ("split", "squat"): (M("sentadilla dividida", "f"),),
    ("split", "squats"): (M("sentadilla dividida", "f"),),
    ("quarter", "sit", "up"): (M("abdominal de un cuarto"),),
    ("janda", "sit", "up"): (M("abdominal Janda"),),
    ("jackknife", "sit", "up"): (M("abdominal navaja"),),
    ("jack", "knife"): (M("navaja", "f"),),
    ("diamond", "push", "up"): (M("flexión", "f"), GRIP("de diamante")),
    ("clap", "push", "up"): (M("flexión con palmada", "f"),),
    ("clock", "push", "up"): (M("flexión del reloj", "f"),),
    ("plyo", "push", "up"): (M("flexión pliométrica", "f"),),
    ("plyo", "squat"): (M("sentadilla pliométrica", "f"),),
    ("superman", "push", "up"): (M("flexión Superman", "f"),),
    ("handstand", "push", "up"): (M("flexión en parada de manos", "f"),),
    ("french", "press"): (M("press francés"),),
    ("tate", "press"): (M("press Tate"),),
    ("scott", "press"): (M("press Scott"),),
    ("guillotine", "bench", "press"): (M("press de banca guillotina"),),
    ("skull", "press"): (M("press al cráneo"),),
    ("inverted", "row"): (M("remo invertido"),),
    ("v", "sit"): (M("V-sit"),),
    ("l", "sit"): (M("L-sit"),),
    ("one", "legged"): (UNI("a una pierna"),),
    ("leg", "raised"): (EXTRA("con la pierna elevada"),),
    ("legs", "raised"): (EXTRA("con las piernas elevadas"),),
    ("arms", "extended"): (EXTRA("con los brazos extendidos"),),
    ("arm", "extended"): (EXTRA("con el brazo extendido"),),
    ("leg", "extended"): (EXTRA("con la pierna extendida"),),
    ("tennis", "ball"): (EQUIP("con pelota de tenis"),),
    ("between", "ankles"): (EXTRA("entre los tobillos"),),
    ("between", "knees"): (EXTRA("entre las rodillas"),),
    ("around", "world"): (M("vuelta al mundo", "f"),),
    ("around", "the", "world"): (M("vuelta al mundo", "f"),),
    ("cross", "trainer"): (EQUIP("en elíptica"),),
    ("sledge", "hammer"): (EQUIP("con mazo"),),
    ("figure", "8"): (EXTRA("en ocho"),),
    ("full", "can"): (STYLE("full can"),),
    ("iron", "cross"): (M("cruz de hierro", "f"),),
    ("anti", "gravity"): (EXTRA("antigravedad"),),
    ("captains", "chair"): (EQUIP("en silla de capitán"),),
    ("wind", "sprints"): (M("sprints"),),
    ("scissor", "jumps"): (M("saltos de tijera", "mp"),),
    ("depth", "jump"): (M("salto en profundidad"),),
    ("body", "saw"): (M("sierra corporal", "f"),),
    ("two", "one", "leg", "curl"): (M("curl femoral"), EXTRA("dos a uno")),
    ("two", "toe", "touch"): (M("toque de dos puntas"),),
    ("waiter", "biceps", "curl"): (M("curl de bíceps de camarero"),),
    ("waiter", "curl"): (M("curl de camarero"),),
    ("kipping", "muscle", "up"): (M("muscle-up con kipping"),),
    ("impossible", "dips"): (M("fondos imposibles", "mp"),),
    ("frog", "crunch"): (M("crunch rana"),),
    ("frog", "planche"): (M("planche rana", "f"),),
    ("side", "to", "side", "chin"): (M("dominada supina de lado a lado", "f"),),
    ("gironda", "sternum", "chin"): (M("dominada al esternón Gironda", "f"),),
    ("gorilla", "chin"): (M("dominada gorila", "f"),),
    ("balance", "board"): (EQUIP("en tabla de equilibrio"),),
    ("cambered", "bar"): (EQUIP("con barra curva"),),
    ("pro", "lat", "bar"): (EQUIP("con barra ancha pro"),),
    ("sz", "bar"): (EQUIP("con barra SZ"),),
    ("3", "point"): (EXTRA("a tres puntos"),),
    ("point", "stance"): (EXTRA("de apoyo"),),
    ("wide", "angle"): (EXTRA("de ángulo abierto"),),
    ("short", "stride"): (EXTRA("de zancada corta"),),
    ("semi", "squat"): (M("semi sentadilla", "f"),),
    ("drop", "jump"): (M("salto con caída"),),
    ("box", "jump"): (M("salto al cajón"),),
})
_expand_overlapping_unis()


def phrase_score(length: int, pieces: tuple[Piece, ...]) -> int:
    has_move = any(piece.kind == "move" for piece in pieces)
    return length * length + (30 * length if has_move else 0)


def is_num(token: str) -> bool:
    return bool(re.fullmatch(r"\d+°|\d+/\d+|\d+", token))


def tokenize(text: str) -> list[str]:
    return re.findall(r"\d+/\d+|\d+°|\d+|[a-z0-9]+", text.lower())


def segment(tokens: list[str]) -> list[tuple]:
    n = len(tokens)
    best = [-10**9] * (n + 1)
    best[n] = 0
    choice: list[tuple | None] = [None] * n
    for i in range(n - 1, -1, -1):
        max_l = min(6, n - i)
        for length in range(max_l, 1, -1):
            gram = tuple(tokens[i:i + length])
            pieces = PHRASES.get(gram)
            if not pieces:
                continue
            score = phrase_score(length, pieces) + best[i + length]
            if score > best[i]:
                best[i] = score
                choice[i] = (length, "pieces", pieces)
        token = tokens[i]
        candidates: list[tuple] = []
        if token in WORDS:
            candidates.append((phrase_score(1, WORDS[token]) + best[i + 1], 1, "pieces", WORDS[token]))
        if token in CONJ:
            candidates.append((0.2 + best[i + 1], 1, "conj", CONJ[token]))
        if token in STOP:
            candidates.append((0.05 + best[i + 1], 1, "stop", token))
        if is_num(token):
            candidates.append((1 + best[i + 1], 1, "num", token))
        candidates.append((0.01 + best[i + 1], 1, "unk", token))
        for score, length, tag, payload in candidates:
            if score > best[i]:
                best[i] = score
                choice[i] = (length, tag, payload)
    if any(item is None for item in choice):
        raise RuntimeError("segmentación incompleta")
    return choice  # type: ignore[return-value]


def consume(tokens: list[str]) -> tuple[list[Piece], list[str]]:
    if not tokens:
        return [], []
    choice = segment(tokens)
    pieces: list[Piece] = []
    unknowns: list[str] = []
    pending = ""
    i = 0
    while i < len(tokens):
        length, tag, payload = choice[i]
        if tag == "conj":
            pending = payload
            i += length
            continue
        if tag == "stop":
            i += length
            continue
        if tag == "unk":
            unknowns.append(payload)
            piece = Piece("extra", payload)
        elif tag == "num":
            shown = f"a {payload}" if "°" in payload else payload
            piece = Piece("num", shown)
            pieces.append(piece)
            pending = ""
            i += length
            continue
        else:
            attached = False
            for piece in payload:
                if pending and not attached:
                    if piece.kind == "move":
                        piece = piece._replace(conj=pending)
                    elif piece.kind == "muscle":
                        rest = re.sub(r"^(de|del)\s+", "", piece.es)
                        piece = piece._replace(es=f"{pending} {rest}")
                    else:
                        piece = piece._replace(es=f"{pending} {piece.es}")
                    pending = ""
                    attached = True
                if piece.es:
                    pieces.append(piece)
            i += length
            continue
        if pending and piece.kind == "extra":
            piece = piece._replace(es=f"{pending} {piece.es}")
            pending = ""
        if piece.es:
            pieces.append(piece)
        i += length
    return pieces, unknowns


def inflect(text: str, gender: str) -> str:
    if text.startswith("@"):
        table = AGREE[text[1:]]
        return table[gender if gender in table else "m"]
    return text


def muscle_key(text: str) -> str:
    return re.sub(r"^(de|del|y|a)\s+", "", text)


def pick_head(group: list[Piece]) -> int:
    for index in range(len(group) - 1, -1, -1):
        if not group[index].modifier:
            return index
    return len(group) - 1


def assemble(pieces: list[Piece]) -> str:
    moves = [piece for piece in pieces if piece.kind == "move"]
    groups: list[list[Piece]] = [[]]
    for piece in moves:
        if piece.conj and groups[-1]:
            groups.append([piece])
        else:
            groups[-1].append(piece)
    groups = [group for group in groups if group]

    heads: list[str] = []
    gender = "m"
    secondaries: list[str] = []
    for index, group in enumerate(groups):
        head_index = pick_head(group)
        head = group[head_index]
        text = head.es
        if index == 0:
            gender = head.gender
        elif head.conj:
            text = f"{head.conj} {text}"
        heads.append(text)
        for piece_index, piece in enumerate(group):
            if piece_index == head_index:
                continue
            secondaries.append(piece.es if piece.es.startswith("con ") else f"con {piece.es}")

    head_es = " ".join(heads)
    muscles: list[str] = []
    for piece in pieces:
        if piece.kind != "muscle":
            continue
        key = muscle_key(piece.es)
        if key and key in head_es:
            continue
        muscles.append(piece.es)
    styles = [piece.es for piece in pieces if piece.kind == "style" and piece.es not in head_es]
    adjectives = [inflect(piece.es, gender) for piece in pieces if piece.kind == "adj"]
    numbers = [piece.es for piece in pieces if piece.kind == "num"]
    grips = [piece.es for piece in pieces if piece.kind == "grip" and piece.es not in ("con agarre", "con agarre ")]
    unis = [piece.es for piece in pieces if piece.kind == "uni"]
    positions = [inflect(piece.es, gender) for piece in pieces if piece.kind == "pos"]
    extras = [inflect(piece.es, gender) for piece in pieces if piece.kind == "extra" and piece.es]
    equips = [piece.es for piece in pieces if piece.kind == "equip"]

    if any("pierna" in uni for uni in unis):
        muscles = [item for item in muscles if muscle_key(item) not in {"pierna", "piernas"}]
    if any("brazo" in uni or "mano" in uni for uni in unis):
        muscles = [item for item in muscles if muscle_key(item) not in {"brazo", "brazos", "mano", "manos"}]
    if any(uni in {"a un brazo", "a una mano"} for uni in unis):
        equips = ["con mancuerna" if item == "con mancuernas" else item for item in equips]

    specific_bar = any(item.startswith("con barra ") or item == "con barra Z" for item in equips + extras)
    if specific_bar:
        equips = [item for item in equips if item != "con barra"]
    if any("Smith" in item for item in equips):
        equips = [item for item in equips if item != "en máquina"]
    if "en banco plano" in equips:
        equips = [item for item in equips if item != "en banco"]
    if "en polea alta" in equips or "en polea baja" in equips or "polea" in head_es:
        equips = [item for item in equips if item != "en polea"]
    if "banca" in head_es or "banco" in head_es:
        equips = [item for item in equips if item not in {"en banco", "en banco plano"}]

    def unique(items: list[str]) -> list[str]:
        seen: list[str] = []
        for item in items:
            cleaned = item.strip()
            if cleaned and cleaned not in seen:
                seen.append(cleaned)
        return seen

    parts = unique(
        [head_es]
        + muscles
        + styles
        + adjectives
        + secondaries
        + numbers
        + grips
        + unis
        + positions
        + extras
        + equips
    )
    text = re.sub(r"\s+", " ", " ".join(parts)).strip()
    text = text.replace("con con ", "con ").replace("de de ", "de ")
    return text


def translate_core(text: str) -> tuple[str, list[str]]:
    pieces, unknowns = consume(tokenize(text))
    return assemble(pieces), unknowns


def translate(name: str) -> tuple[str, list[str]]:
    key = re.sub(r"\s+", " ", name.strip().lower())
    if key in OVERRIDES:
        return OVERRIDES[key], []

    text = name.replace("в°", "°").replace("º", "°")
    text = text.replace("'", "").replace("’", "")
    version = ""
    version_match = re.search(r"\bv\.\s*(\d+)\b", text, flags=re.I)
    if version_match:
        version = f"v. {version_match.group(1)}"
        text = f"{text[:version_match.start()]} {text[version_match.end():]}"

    parens = re.findall(r"\(([^)]*)\)", text)
    text = re.sub(r"\([^)]*\)", " ", text)

    gender_note = ""
    gender_match = re.search(r"\b(male|female)\b", text, flags=re.I)
    if gender_match:
        gender_note = "(hombre)" if gender_match.group(1).lower() == "male" else "(mujer)"
        text = f"{text[:gender_match.start()]} {text[gender_match.end():]}"

    text = text.replace("–", " ").replace("—", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text).strip(" -")

    unknowns: list[str] = []
    core, core_unknowns = translate_core(text)
    unknowns.extend(core_unknowns)
    rendered_parens: list[str] = []
    for paren in parens:
        inner, inner_unknowns = translate_core(paren.replace("-", " "))
        unknowns.extend(inner_unknowns)
        if inner:
            rendered_parens.append(f"({inner})")

    parts = [part for part in [core, *rendered_parens, gender_note, version] if part]
    spanish = re.sub(r"\s+", " ", " ".join(parts)).strip()
    if not spanish:
        spanish = name.strip()
    return spanish, unknowns


def explain(name: str) -> str:
    spanish, unknowns = translate(name)
    text = name.replace("-", " ")
    pieces, _ = consume(tokenize(text))
    detail = ", ".join(f"{piece.kind}:{piece.es}" for piece in pieces) or "(vacío)"
    unknown = f" desconocidas={unknowns}" if unknowns else ""
    return f"{name}\n  → {spanish}\n  {detail}{unknown}"


def check_expect() -> list[str]:
    failures = []
    for english, want in EXPECT.items():
        got, _ = translate(english)
        if got != want:
            failures.append(f"  {english}\n    esperado: {want}\n    obtuvo:   {got}")
    return failures


def load_exercises() -> list[dict]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def with_names(exercise: dict, spanish: str) -> dict:
    updated: dict = {}
    english = exercise["name"]
    if isinstance(english, dict):
        english = english.get("en") or next(iter(english.values()))
    for key, value in exercise.items():
        if key == "names":
            continue
        updated[key] = value
        if key == "name":
            updated["names"] = {"en": english, "es": spanish}
    return updated


def review() -> int:
    exercises = load_exercises()
    unknown_examples: dict[str, list[str]] = {}
    translated = 0
    for exercise in exercises:
        spanish, unknowns = translate(exercise["name"])
        translated += 1
        for token in unknowns:
            unknown_examples.setdefault(token, [])
            if len(unknown_examples[token]) < 3:
                unknown_examples[token].append(exercise["name"])
        if not spanish:
            print(f"vacío: {exercise['name']}")

    failures = check_expect()
    print(f"ejercicios: {translated}")
    print(f"frases del glosario: {len(PHRASES)}  palabras: {len(WORDS)}")
    if failures:
        print(f"\npruebas fallidas ({len(failures)}):")
        print("\n".join(failures))
    else:
        print("pruebas de ejemplo: ok")
    if unknown_examples:
        print(f"\npalabras sin glosario ({len(unknown_examples)}):")
        for token in sorted(unknown_examples):
            samples = " | ".join(unknown_examples[token])
            print(f"  {token}: {samples}")
    else:
        print("palabras sin glosario: 0")

    print("\nejemplos:")
    shown = exercises[:8] + exercises[200:204] + sorted(exercises, key=lambda item: len(item["name"]), reverse=True)[:8]
    seen = set()
    for exercise in shown:
        if exercise["id"] in seen:
            continue
        seen.add(exercise["id"])
        spanish, _ = translate(exercise["name"])
        print(f"  {exercise['name']}\n    {spanish}")
    return 1 if failures or unknown_examples else 0


def apply() -> int:
    status = review()
    if status != 0:
        print("\nno escribí nada: todavía hay palabras sin glosario o pruebas fallidas")
        return status
    exercises = load_exercises()
    updated = []
    for exercise in exercises:
        spanish, _ = translate(exercise["name"])
        updated.append(with_names(exercise, spanish))
    DATA_PATH.write_text(
        json.dumps(updated, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    html = HTML_PATH.read_text(encoding="utf-8")
    start = html.find("const EXERCISES = ")
    end = html.find(";\n", start)
    if start < 0 or end < 0:
        raise SystemExit("no encontré el catálogo embebido en index.html")
    blob = json.dumps(updated, ensure_ascii=False, separators=(",", ":"))
    HTML_PATH.write_text(html[:start] + "const EXERCISES = " + blob + html[end:], encoding="utf-8")
    print(f"\nescribí {len(updated)} nombres en {DATA_PATH.name} y en el visor")
    return 0


def main() -> int:
    if "--explain" in sys.argv:
        index = sys.argv.index("--explain")
        print(explain(sys.argv[index + 1]))
        return 0
    if "--apply" in sys.argv:
        return apply()
    return review()


if __name__ == "__main__":
    sys.exit(main())
