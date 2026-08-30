# What the brochure says, in English and Spanish, kept apart from how it looks.
#
# Every line here is answerable from app/catalog.json -- the products the school
# actually sells -- or from the logo itself (est. 2009, Playa Venao, Panama).
# Nothing claims a schedule, a transport arrangement or a price, because those
# change and a printed sheet cannot follow them. Prices in particular are left
# out on purpose: the sheet outlives the price list, and the QR code goes to the
# booking page where the current ones live.

BOOKING_URL = "https://shokogimanager.com/book.html"
BOOKING_LABEL = "shokogimanager.com/book.html"
EMAIL = "shokogipanama@gmail.com"

COVER = {
    "eyebrow": "EST. 2009 · PLAYA VENAO · PANAMÁ",
    "wordmark": "SHOKOGI",
    "sub_en": "SURF SCHOOL",
    "sub_es": "ESCUELA DE SURF",
    "tagline_en": "Learn to surf, or surf better, on the Pacific coast of Panama.",
    "tagline_es": "Aprende a surfear, o surfea mejor, en la costa pacífica de Panamá.",
    "scan_en": "SCAN TO BOOK",
    "scan_es": "ESCANEA PARA RESERVAR",
    # The whole offer in one breath, so the cover answers "what is this?" before
    # anyone turns the page. Two lines, because seven items on one wrap badly.
    "offer_eyebrow": "WHAT WE DO · LO QUE HACEMOS",
    "offer": [
        "SURF LESSONS · LESSON PACKS · YOUNG GUNS · SURF TRIPS",
        "SUP · FOIL TOW-IN · VIDEO ANALYSIS · YOGA & PILATES · ICE BATH",
        "PHOTO & VIDEO · BOARD RENTAL",
    ],
}

# The strip that closes the two service pages: the same offer as the cover's QR,
# put where someone has just finished reading about something they want.
CTA = {
    "title_en": "Book any of this online",
    "title_es": "Reserva todo esto en línea",
    "body_en": "Prices, availability and your booking, in a couple of minutes.",
    "body_es": "Precios, disponibilidad y tu reserva, en un par de minutos.",
}

# Page two: everything built around a surfboard and an instructor.
SURF = {
    "eyebrow": "LESSONS & COACHING · CLASES Y ENTRENAMIENTO",
    "title_en": "In the water",
    "title_es": "En el agua",
    "lede_en": "Every lesson comes with a surfboard and a lycra, and an instructor "
               "who stays in the water with you.",
    "lede_es": "Cada clase incluye tabla y licra, y un instructor que se queda "
               "en el agua contigo.",
    "cards": [
        ("board", "PRIVATE SURF LESSON", "CLASE PRIVADA DE SURF",
         "One hour, one to one. Board and lycra included. "
         "A longer hour-and-a-half session is there when you want the extra water time.",
         "Una hora, uno a uno. Tabla y licra incluidas. "
         "También hay una sesión de hora y media cuando quieras más tiempo en el agua."),
        ("people", "BRING A FRIEND", "VEN CON UN AMIGO",
         "The same lesson, shared with one or two others. "
         "Less per person, and a lot more fun on the way back in.",
         "La misma clase, compartida con una o dos personas más. "
         "Menos por persona, y mucho más divertido al volver."),
        ("stack", "LESSON PACKS", "PAQUETES DE CLASES",
         "Two, three, four, five, six, seven or ten lessons. "
         "The same coach every time, so the week builds on itself instead of starting over.",
         "Dos, tres, cuatro, cinco, seis, siete o diez clases. "
         "El mismo coach siempre, para que la semana avance en vez de empezar de cero."),
        ("video", "VIDEO ANALYSIS", "ANÁLISIS DE VIDEO",
         "We film your session, then sit down and go through it with you. "
         "The theory session that goes with it is free.",
         "Filmamos tu sesión y luego la repasamos contigo. "
         "La sesión de teoría que la acompaña es gratuita."),
        ("sun", "YOUNG GUNS & SUMMER CAMPS", "YOUNG GUNS Y CAMPAMENTOS",
         "Our programme for kids, at their pace and on the right board for them. "
         "Camps run through the summer season.",
         "Nuestro programa para niños, a su ritmo y con la tabla adecuada. "
         "Los campamentos funcionan durante la temporada de verano."),
        ("pin", "SURF TRIP", "SURF TRIP",
         "A guided day away from Venao, to whichever break along the coast is working "
         "that morning.",
         "Un día guiado fuera de Venao, al break de la costa que esté funcionando "
         "esa mañana."),
    ],
}

# Page three: the rest of what the school does, on and off the board.
MORE = {
    "eyebrow": "BEYOND THE SURFBOARD · MÁS ALLÁ DE LA TABLA",
    "title_en": "More than surf",
    "title_es": "Más que surf",
    "lede_en": "Flat morning, tired legs, or a camera pointed at your best wave of the trip.",
    "lede_es": "Mañana sin olas, piernas cansadas, o una cámara apuntando a tu mejor ola del viaje.",
    "cards": [
        ("paddle", "SUP LESSONS", "CLASES DE SUP",
         "Stand-up paddle, one hour or an hour and a half, board and lycra included. "
         "The right call on a glassy morning.",
         "Stand-up paddle, una hora o una hora y media, tabla y licra incluidas. "
         "La mejor opción en una mañana de mar plano."),
        ("foil", "FOIL TOW-IN", "FOIL TOW-IN",
         "One- and two-hour tow-in foil sessions, and foil rental once you have it. "
         "The closest thing to flying we sell.",
         "Sesiones de foil tow-in de una y dos horas, y alquiler de foil cuando ya lo domines. "
         "Lo más parecido a volar que ofrecemos."),
        ("yoga", "YOGA & PILATES", "YOGA Y PILATES",
         "Single classes, on the mat, to open up the shoulders and hips that surfing "
         "keeps asking for.",
         "Clases sueltas, sobre la colchoneta, para abrir los hombros y las caderas "
         "que el surf siempre exige."),
        ("ice", "ICE BATH", "BAÑO DE HIELO",
         "A cold plunge after the session. Legs come back quicker, and the head clears "
         "on the way.",
         "Una inmersión fría después de la sesión. Las piernas se recuperan antes, "
         "y la cabeza se despeja."),
        ("camera", "PHOTO & VIDEO", "FOTO Y VIDEO",
         "Photos from the beach or from the water beside you, video of your session, "
         "or a private shoot of your own.",
         "Fotos desde la playa o desde el agua a tu lado, video de tu sesión, "
         "o una sesión de fotos privada."),
        ("globe", "YOUR INSTRUCTORS", "TUS INSTRUCTORES",
         "English, Spanish and French between the crew, and a team that lives and "
         "surfs this beach year round.",
         "Inglés, español y francés en el equipo, y gente que vive y surfea "
         "esta playa todo el año."),
    ],
}

# Page four, top half: what a visitor can walk out with.
RENTALS = {
    "eyebrow": "BOARD RENTAL · ALQUILER DE TABLAS",
    "title_en": "Take one out",
    "title_es": "Llévate una",
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

# Page four, middle: the six things worth knowing before walking down.
KNOW = {
    "eyebrow": "GOOD TO KNOW · BUENO SABER",
    "items": [
        ("Board and lycra come with every lesson.",
         "Tabla y licra incluidas en cada clase."),
        ("All levels. First time on a board is welcome.",
         "Todos los niveles. Tu primera vez es bienvenida."),
        ("English · Español · Français.",
         "Inglés · Español · Francés."),
        ("Session times follow the tide, so they move day to day — booking ahead "
         "gets you the best window.",
         "Los horarios siguen la marea y cambian cada día — reservar con antelación "
         "te da la mejor ventana."),
        ("Bring swimwear, sunscreen and water. We have the rest.",
         "Trae traje de baño, protector solar y agua. Lo demás lo tenemos nosotros."),
        ("Playa Venao, Panamá. Teaching this beach since 2009.",
         "Playa Venao, Panamá. Enseñando en esta playa desde 2009."),
    ],
}

BOOK = {
    "eyebrow": "BOOK ONLINE · RESERVA EN LÍNEA",
    "title_en": "Point your camera here",
    "title_es": "Apunta tu cámara aquí",
    "body_en": "The booking page has everything above with today's prices, "
               "and takes your booking in a couple of minutes.",
    "body_es": "La página de reservas tiene todo lo anterior con los precios de hoy, "
               "y toma tu reserva en un par de minutos.",
    "or_en": "Or write to us:",
    "or_es": "O escríbenos:",
}
