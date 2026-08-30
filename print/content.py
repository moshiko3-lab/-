# What the brochure says, in English and Spanish, kept apart from how it looks.
#
# Every line here is answerable from app/catalog.json -- the products the school
# actually sells -- or from the logo itself (est. 2009, Playa Venao, Panama).
# Nothing claims a schedule, a transport arrangement or a price, because those
# change and a printed sheet cannot follow them. Prices in particular are left
# out on purpose: the sheet outlives the price list, and the QR code goes to the
# booking page where the current ones live.
#
# The Spanish is not a caption under the English. It is the same sentence said
# again, and it is set at the same size wherever the page has room for it,
# because half the people who pick this up in a room in Venao will read that
# column first.

# The school's own shop, confirmed against the connected Shopify store rather
# than typed from memory: 285 products, prices, and a checkout. The booking
# page this repository builds sells two of those products, so a brochure
# promising "the full list with today's prices" has to point here.
BOOKING_URL = "https://www.shokogi.com"
BOOKING_LABEL = "shokogi.com"
EMAIL = "shokogipanama@gmail.com"

# ---------------------------------------------------------------- 1. cover
COVER = {
    "wordmark": "SHOKOGI",
    "rule_en": "SURF SCHOOL",
    "rule_es": "ESCUELA DE SURF",
    "place": "PLAYA VENAO · PANAMÁ",
    "est": "EST. 2009",
    # the school's own pin, off app/catalog.json, in the notation a surf guide
    # would use rather than the decimal one a database stores
    "coords": "07°25′42″ N · 80°11′23″ W",
    # the words that go round the patch on the cover
    "patch_top": "SHOKOGI SURF SCHOOL",
    "patch_bottom": "PLAYA VENAO PANAMA",
    "patch2_top": "SCHOOL SINCE 2009",
    "patch2_bottom": "EVERY LEVEL WELCOME",
}

# ------------------------------------------------------------- 2. the place
OPENING = {
    "eyebrow": "THE PLACE · EL LUGAR",
    "display_en": "Learn the ocean,\nnot just the wave.",
    "display_es": "Aprende el océano,\nno sólo la ola.",
    "body_en": [
        "Playa Venao is a long sand bay on the Pacific side of the Azuero "
        "peninsula, and it breaks almost every day of the year. It is patient "
        "water. Nobody has to be talked into their first wave here.",
        "We have taught on this beach since 2009. Every lesson is an instructor "
        "in the water beside you rather than a voice from the sand, and every "
        "lesson comes with the board and the lycra for it.",
        "A first lesson is an hour. The board under you on the sand, then the "
        "whitewater, then the moment you stop thinking about your feet.",
    ],
    "body_es": [
        "Playa Venao es una bahía larga de arena en el Pacífico de la península "
        "de Azuero, y rompe casi todos los días del año. Es agua paciente. "
        "Aquí a nadie hay que convencerlo de tomar su primera ola.",
        "Enseñamos en esta playa desde 2009. Cada clase es un instructor en el "
        "agua a tu lado, no una voz desde la arena, y cada clase viene con la "
        "tabla y la licra para darla.",
        "Una primera clase es una hora. La tabla bajo ti en la arena, luego la "
        "espuma, y luego el momento en que dejas de pensar en tus pies.",
    ],
    # ISA Level 1 & 2 and the ten years are the school's own claim on
    # shokogi.com; the languages are the staff roster in app/catalog.json plus
    # the Hebrew their site names.
    "facts": [
        ("SINCE 2009", "DESDE 2009"),
        ("ISA LEVEL 1 & 2", "INSTRUCTORES ISA"),
        ("EVERY LEVEL", "TODOS LOS NIVELES"),
        ("EN · ES · HE · FR", "CUATRO IDIOMAS"),
    ],
}

# ------------------------------------------------------------------ 3. surf
SURF = {
    "eyebrow": "LESSONS & COACHING · CLASES Y ENTRENAMIENTO",
    "title_en": "In the water",
    "title_es": "En el agua",
    "lede_en": "Board and lycra included, always. An hour is the usual first "
               "lesson; an hour and a half is there when you want the water time.",
    "lede_es": "Tabla y licra siempre incluidas. Una hora es la primera clase "
               "habitual; hora y media está ahí cuando quieras más agua.",
    "items": [
        ("PRIVATE LESSON", "CLASE PRIVADA",
         "One hour, one instructor, one of you. The fastest way to stop fighting "
         "the board and start reading the water.",
         "Una hora, un instructor, tú. La manera más rápida de dejar de pelear "
         "con la tabla y empezar a leer el agua."),
        ("SHARED LESSON", "CLASE COMPARTIDA",
         "The same hour, taken with one or two others. Less per person, and "
         "better company on the paddle back out.",
         "La misma hora, con una o dos personas más. Menos por persona, y mejor "
         "compañía al remar de vuelta."),
        ("LESSON COURSES", "CURSOS",
         "Two, three, five, seven, ten or fifteen lessons. The same coach each "
         "time, so a week builds instead of starting over every morning.",
         "Dos, tres, cinco, siete, diez o quince clases. El mismo coach cada vez, "
         "para que la semana avance en vez de empezar de cero cada mañana."),
        ("VIDEO ANALYSIS", "ANÁLISIS DE VIDEO",
         "Filmed from the beach, then watched back with your instructor. The "
         "theory session that goes with it costs nothing.",
         "Filmado desde la playa y visto después con tu instructor. La sesión de "
         "teoría que lo acompaña no cuesta nada."),
    ],
}

START = {
    "eyebrow": "WHERE TO START · POR DÓNDE EMPEZAR",
    "items": [
        ("NEVER SURFED", "NUNCA HAS SURFEADO",
         "One private hour, on foam.", "Una hora privada, sobre espuma."),
        ("A FEW TIMES", "ALGUNAS VECES",
         "A pack of three to five.", "Un paquete de tres a cinco."),
        ("YOU CAN STAND UP", "YA TE PARAS",
         "Video analysis, then a shorter board.",
         "Análisis de video, y luego una tabla más corta."),
        ("JUST WANT A BOARD", "SÓLO QUIERES TABLA",
         "Take one out by the hour.", "Llévate una por hora."),
    ],
}

# ----------------------------------------------------------------- 4. camps
#
# Every duration below is a product on shokogi.com, read off the store rather
# than guessed. What a camp includes is not claimed here: the durations are
# public and the inclusions change, so the code carries a reader to the page
# that lists them.
CAMPS = {
    "eyebrow": "CAMPS · CAMPAMENTOS",
    "title_en": "Come for a week",
    "title_es": "Ven por una semana",
    "lede_en": "A camp is a run of days rather than an hour of one, and the "
               "difference shows on about the third morning.",
    "lede_es": "Un campamento es una serie de días en vez de una hora suelta, y "
               "la diferencia se nota más o menos la tercera mañana.",
    "groups": [
        ("SURF CAMP", "CAMPAMENTO DE SURF", "7 · 10 · 15",
         "DAYS · DÍAS",
         "Seven, ten or fifteen days of surfing, in the water every day it is "
         "worth being in.",
         "Siete, diez o quince días de surf, en el agua cada día que valga la pena."),
        ("YOUNG CAMP", "CAMPAMENTO INFANTIL", "1 → 35",
         "DAYS · DÍAS",
         "Our kids' camp, from a single day to thirty-five of them, at their own "
         "pace and on the right board.",
         "Nuestro campamento infantil, de un día suelto a treinta y cinco, a su "
         "ritmo y con la tabla adecuada."),
        ("TEENS CAMP", "CAMPAMENTO JUVENIL", "1 · 5 · 10 · 15",
         "DAYS · DÍAS",
         "The same idea for the ones who are too old for the young camp and too "
         "young to be left to it.",
         "La misma idea para quienes ya son grandes para el infantil y todavía "
         "chicos para ir solos."),
        ("FAMILY CAMPS", "CAMPAMENTOS FAMILIARES", "ALL", "TODOS",
         "Book the young camp and the teens camp together and the whole family "
         "is in the water at once.",
         "Reserva el infantil y el juvenil juntos y toda la familia entra al agua "
         "a la vez."),
    ],
    "note_en": "What each camp includes is on the site, and it moves with the season.",
    "note_es": "Lo que incluye cada campamento está en el sitio, y cambia con la temporada.",
}

# ---------------------------------------------------------------- 5. beyond
BEYOND = {
    "eyebrow": "FOIL & THE REST · FOIL Y LO DEMÁS",
    "title_en": "The rest of\nthe day",
    "title_es": "El resto del día",
    "items": [
        ("FOIL TOW-IN", "FOIL TOW-IN",
         "One- and two-hour sessions behind the ski, and foil rental once you "
         "have it. The closest thing to flying we sell.",
         "Sesiones de una y dos horas detrás de la moto, y alquiler de foil "
         "cuando ya lo domines. Lo más parecido a volar que ofrecemos."),
        ("SUP", "SUP",
         "Stand-up paddle, one hour or an hour and a half.",
         "Stand-up paddle, una hora u hora y media."),
        ("YOGA & PILATES", "YOGA Y PILATES",
         "Single classes, for the shoulders and hips surfing asks for.",
         "Clases sueltas, para los hombros y caderas que el surf exige."),
        ("ICE BATH", "BAÑO DE HIELO",
         "A cold plunge when the session has taken more than it gave.",
         "Una inmersión fría cuando la sesión pidió más de lo que dio."),
        ("PHOTO & VIDEO", "FOTO Y VIDEO",
         "From the sand, from the water beside you, from the ski, or from a "
         "drone overhead. Private shoots too.",
         "Desde la arena, desde el agua a tu lado, desde la moto, o desde un "
         "dron. También sesiones privadas."),
        ("SURF TRIP", "SURF TRIP",
         "A guided day to whichever break along the coast is working. Custom "
         "trips are on the site.",
         "Un día guiado al break de la costa que esté funcionando. Los viajes a "
         "medida están en el sitio."),
    ],
}

# ---------------------------------------------------------------- 5. quiver
#
# The numbers on this page are not written here. quiver.py counts them off
# app/catalog.json, so a rebuild after the next inventory export prints
# whatever is true then rather than whatever was true the day this was typed.
RENTALS = {
    "eyebrow": "THE QUIVER · EL QUIVER",
    "title_en": "Take one out",
    "title_es": "Llévate una",
    "lede_en": "Every board the school owns, counted off its own rack. Foam to "
               "start on, fibreglass when you are ready for it, and a long list "
               "of things in between.",
    "lede_es": "Cada tabla que tiene la escuela, contada de su propio rack. "
               "Espuma para empezar, fibra cuando estés listo, y una lista larga "
               "de cosas en medio.",
    "stat_boards": ("BOARDS", "TABLAS"),
    "stat_range": ("NOSE TO TAIL", "DE LARGO"),
    "stat_shapers": ("SHAPERS", "SHAPERS"),
    "chart_en": "How many of each length, foam and fibreglass.",
    "chart_es": "Cuántas de cada largo, espuma y fibra.",
    "legend": ("HARD · FIBRA", "SOFT · ESPUMA"),
    "racks_en": "In the racks",
    "racks_es": "En el rack",
    "note_en": "By the hour, or keep it until closing time.",
    "note_es": "Por hora, o quédatela hasta la hora de cierre.",
    "items": [
        ("SOFT-BOARDS", "Tablas blandas"),
        ("FUN-BOARDS", "Fun-boards"),
        ("SHORT-BOARDS", "Tablas cortas"),
        ("HIGH PERFORMANCE", "Alto rendimiento"),
        ("LONGBOARDS", "Longboards"),
        ("SUP", "SUP"),
        ("BODYBOARDS", "Bodyboards"),
        ("FOIL", "Foil"),
    ],
}

# The facts strip on page two already says what is included, what levels we
# take and what languages we speak. These are the two things it does not, and
# they belong last, next to the code somebody is about to scan.
# ----------------------------------------------------------------- 7. shop
#
# Read off the connected Shopify store: the brands are collections on
# shokogi.com, not a list somebody remembered.
SHOP = {
    "eyebrow": "THE SHOP · LA TIENDA",
    "title_en": "New and used",
    "title_es": "Nuevas y usadas",
    "lede_en": "The same building the boards come out of sells them. New boards "
               "from the shapers below, second-hand ones off our own rack, and "
               "everything you have to buy twice because you left the first one "
               "on a plane.",
    "lede_es": "El mismo local de donde salen las tablas también las vende. "
               "Tablas nuevas de los shapers de abajo, usadas de nuestro propio "
               "rack, y todo lo que uno acaba comprando dos veces porque olvidó "
               "lo primero en un avión.",
    "blocks": [
        ("NEW BOARDS", "TABLAS NUEVAS",
         "TORQ · OCEAN MONKEY · FIREWIRE · SLATER DESIGNS · "
         "HAYDEN SHAPES · STEWART · WALDEN"),
        ("SHOKOGI", "SHOKOGI",
         "T-SHIRTS · TANK TOPS · RASH GUARDS · HATS · BOTTLES"),
        ("HARDWARE", "ACCESORIOS",
         "FCS FINS · TRACTION · BOARD COVERS · WAX · "
         "KAINUI, KAIMANA, ROAM & SLATER LEASHES · DAKINE"),
        ("AND THE ONE YOU FORGET", "Y LO QUE SIEMPRE SE OLVIDA",
         "EDEN SUN BLOCK ZINC"),
    ],
    "note_en": "Second-hand boards move fast and are never the same two weeks "
               "running. Ask, or look on the site.",
    "note_es": "Las tablas usadas se van rápido y nunca son las mismas dos "
               "semanas seguidas. Pregunta, o mira en el sitio.",
    "cta_en": "Buy it here, or on the site.",
    "cta_es": "Cómpralo aquí, o en el sitio.",
}

KNOW = {
    "eyebrow": "BEFORE YOU COME · ANTES DE VENIR",
    "items": [
        ("Session times follow the tide, so they move day to day. "
         "Booking ahead gets you the best window.",
         "Los horarios siguen la marea y cambian cada día. "
         "Reservar con antelación te da la mejor ventana."),
        ("Bring swimwear, sunscreen and water. We have the rest.",
         "Trae traje de baño, protector solar y agua. Lo demás lo tenemos."),
    ],
    "tide_caption_en": "The day's tide. It decides when we go.",
    "tide_caption_es": "La marea del día. Ella decide cuándo entramos.",
}

# ----------------------------------------------------------- 4b / 6. to book
BOOK = {
    "inline_en": "Everything here is bookable online.",
    "inline_es": "Todo esto se reserva en línea.",
    "title_en": "Reserve",
    "title_es": "Reserva",
    "body_en": "Scan for the full list with today's prices, availability, "
               "and a booking that takes about two minutes.",
    "body_es": "Escanea para la lista completa con los precios de hoy, "
               "disponibilidad, y una reserva de unos dos minutos.",
    "or_en": "Or write to us",
    "or_es": "O escríbenos",
    "sign_en": "See you in the water.",
    "sign_es": "Nos vemos en el agua.",
}

FOLIO = [
    None,                                   # the cover carries no folio
    "PLAYA VENAO, PANAMÁ",
    "LESSONS · CLASES",
    "CAMPS · CAMPAMENTOS",
    "FOIL & THE REST · Y LO DEMÁS",
    "THE QUIVER · EL QUIVER",
    "THE SHOP · LA TIENDA",
    None,                                   # nor the back
]
