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

BOOKING_URL = "https://shokogimanager.com/book.html"
BOOKING_LABEL = "shokogimanager.com/book.html"
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
    "facts": [
        ("SINCE 2009", "DESDE 2009"),
        ("EVERY LEVEL", "TODOS LOS NIVELES"),
        ("EN · ES · FR", "TRES IDIOMAS"),
        ("BOARD + LYCRA", "TABLA Y LICRA"),
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
        ("LESSON PACKS", "PAQUETES DE CLASES",
         "Two, three, four, five, six, seven or ten. The same coach each time, "
         "so a week builds instead of starting over every morning.",
         "Dos, tres, cuatro, cinco, seis, siete o diez. El mismo coach cada vez, "
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

# ---------------------------------------------------------------- 4. beyond
BEYOND = {
    "eyebrow": "BEYOND THE BOARD · MÁS ALLÁ DE LA TABLA",
    "title_en": "The rest of\nthe day",
    "title_es": "El resto del día",
    "items": [
        ("SUP", "SUP",
         "Stand-up paddle, one hour or an hour and a half.",
         "Stand-up paddle, una hora u hora y media."),
        ("FOIL TOW-IN", "FOIL TOW-IN",
         "One- and two-hour tow-in sessions, and foil rental after.",
         "Sesiones tow-in de una y dos horas, y alquiler de foil después."),
        ("YOGA & PILATES", "YOGA Y PILATES",
         "Single classes, for the shoulders and hips surfing asks for.",
         "Clases sueltas, para los hombros y caderas que el surf exige."),
        ("ICE BATH", "BAÑO DE HIELO",
         "A cold plunge when the session has taken more than it gave.",
         "Una inmersión fría cuando la sesión pidió más de lo que dio."),
        ("PHOTO & VIDEO", "FOTO Y VIDEO",
         "From the sand or from the water beside you. Private shoots too.",
         "Desde la arena o desde el agua a tu lado. También sesiones privadas."),
        ("YOUNG GUNS", "YOUNG GUNS",
         "Our kids' programme: their own pace, and the right board under them.",
         "Nuestro programa infantil: su propio ritmo, y la tabla adecuada."),
        ("SUMMER CAMPS", "CAMPAMENTOS",
         "Through the summer season, by the day.",
         "Durante la temporada de verano, por día."),
        ("SURF TRIP", "SURF TRIP",
         "A guided day to whichever break along the coast is working.",
         "Un día guiado al break de la costa que esté funcionando."),
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
    "BEYOND THE BOARD · MÁS ALLÁ",
    "THE QUIVER · EL QUIVER",
    None,                                   # nor the back
]
