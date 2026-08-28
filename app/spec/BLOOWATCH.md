# What Bloowatch actually contains

Two machine-made passes, so nothing depends on remembering to click something:

* **97 routes** walked in a signed-in browser, recording every visible button, form field, table column and tab (`tour.json`). 0 failed.
* **1575 interface strings** from the app bundle across 67 groups (`i18n_keys.json`), covering screens that need a record id in the URL and so render blank to a crawler.

This is the build checklist for Shokogi Manager. Nothing here is ticked off yet — the app's README lists what actually works.

## Pages with content

31 of the 97 routes render nothing without a record id; they are omitted below and covered by the string groups at the end.

### `settings/legal`
* Columns: Title, Description
* Controls: Undo, Redo, Formats, Bold, Italic, Text color, Background color, Align left, Align center, Align right, Justify, Bullet list, Numbered list, Decrease indent, Increase indent, Insert/edit link, Insert/edit image, Source code

### `bookings`
* Columns: #id, Name, Activity Calendar, Date Created, Origin, PAX, Total, Due, Status
* Controls: Status, Activity Calendar, Product, Invoiced, Instructor, refresh, columns, 15
* Fields:
  * Search customer Search participants Search booking code `text`
  * Booking Date `text`
  * Session Date `text`

### `settings`
* Controls: $ US Dollar(USD), Logo, Cancel, Save
* Fields:
  * Official Name `text`
  * Tax ID `text`
  * VAT Number `text`
  * Activity Code `text`
  * Address1 `text`
  * Address2 `text`
  * City `text`
  * ZipCode `text`
  * (unlabelled) `select` — options: Country, Afghanistan, Åland Islands, Albania, Algeria, American Samoa
  * Telephone `text`
  * Email `text`
  * Website `text`
  * Commercial Name `text`

### `settings/emails`
* Controls: Undo, Redo, Formats, Bold, Italic, Text color, Background color, Align left, Align center, Align right, Justify, Bullet list, Numbered list, Decrease indent, Increase indent, Insert/edit link, Insert/edit image, Source code

### `settings/sales-templates`
* Controls: Undo, Redo, Formats, Bold, Italic, Text color, Background color, Align left, Align center, Align right, Justify, Bullet list, Numbered list, Decrease indent, Increase indent, Insert/edit link, Insert/edit image, Source code

### `sessions`
* Columns: Name, Creation Date, Participants, Staff, Starting time, Duration
* Controls: Creation Date, Instructor, Activity Calendar, content_copy CLONE, delete Delete, edit Edit, file_downloadExport Table, ADD SESSION, Columns, 25
* Fields:
  * Starting Date `text`

### `manager/staff/new`
* Heading: ADD STAFF
* Columns: Fee Group, Validity Period
* Controls: Assistant, Add a Group, Cancel, SAVE
* Fields:
  * First Name Last Name `text`
  * Role info Define the access rights for this staff. See more information her `text`
  * Telephone `text`
  * Address City `text`
  * Birthday Legal Information info This information will be displayed on Fee S `text`
  * This staff member will be shown on the planning Position in the staff list `text`
  * Activities info Associate a staff to one or more activities. You can create `search`

### `clients`
* Columns: Name, Profile, Telephone, Email, Contact, Total, Due
* Controls: file_download Export CSV, Refresh, Columns, more_vert, 10
* Fields:
  * Search `text`
  * Select CSV file to create users `text`
  * (unlabelled) `file`

### `clients/edit/credit`
* Columns: Name, Profile, Telephone, Email, Contact, Total, Due
* Controls: file_download Export CSV, Refresh, Columns, more_vert, 10
* Fields:
  * Search `text`
  * Select CSV file to create users `text`
  * (unlabelled) `file`

### `partners/new`
* Controls: Cancel, Save
* Fields:
  * Company Name `text`
  * Partner Code `text`
  * First Name `text`
  * Last Name `text`
  * Email `text`
  * Telephone `text`
  * Address1 `text`
  * Address2 `text`
  * City `text`
  * Zip code `text`
  * Country Country Afghanistan Åland Islands Albania Algeria American Samoa An `select` — options: Country, Afghanistan, Åland Islands, Albania, Algeria, American Samoa
  * Tax ID `text`
  * Commission Group Select a Commission Group `select` — options: Select a Commission Group

### `agenda`
* Controls: Activities, + SESSION, keyboard_arrow_down, Today, keyboard_arrow_left, keyboard_arrow_right, settings, filter_list, group, more_vert, more_horiz
* Fields:
  * (unlabelled) `text`
  * search `text`

### `agenda/activities`
* Controls: Activities, + SESSION, keyboard_arrow_down, Today, keyboard_arrow_left, keyboard_arrow_right, settings, filter_list, group, more_vert, more_horiz
* Fields:
  * (unlabelled) `text`
  * search `text`

### `agenda/rental`
* Controls: Activities, + SESSION, keyboard_arrow_down, Today, keyboard_arrow_left, keyboard_arrow_right, settings, filter_list, group, more_vert, more_horiz
* Fields:
  * (unlabelled) `text`
  * search `text`

### `bookings/payments`
* Columns: ID, Name, Order, Payment Date, Payment Note, Recipient, Amount, Method
* Controls: file_download Export CSV, file_downloadExport Report, Refresh, Columns, 25

### `fees`
* Columns: Staff, Code, From, To, Total, Status
* Controls: Instructor, Create A Fee Statement, Refresh, Columns
* Fields:
  * Starting date `text`

### `fiscal`
* Columns: Hour, Activity Calendar, Instructor, Title, Note, Duration, Participants
* Controls: Today, More, Refresh, Columns, more_vert

### `fiscal/archives`
* Columns: Hour, Activity Calendar, Instructor, Title, Note, Duration, Participants
* Controls: Today, More, Refresh, Columns, more_vert

### `fiscal/duplicates`
* Columns: Hour, Activity Calendar, Instructor, Title, Note, Duration, Participants
* Controls: Today, More, Refresh, Columns, more_vert

### `register`
* Columns: Hour, Activity Calendar, Instructor, Title, Note, Duration, Participants
* Controls: Today, More, Refresh, Columns, more_vert

### `register/list`
* Columns: Hour, Activity Calendar, Instructor, Title, Note, Duration, Participants
* Controls: Today, More, Refresh, Columns, more_vert

### `register/pay-in-out`
* Columns: Hour, Activity Calendar, Instructor, Title, Note, Duration, Participants
* Controls: Today, More, Refresh, Columns, more_vert

### `register/tickets`
* Columns: Hour, Activity Calendar, Instructor, Title, Note, Duration, Participants
* Controls: Today, More, Refresh, Columns, more_vert

### `trips/new`
* Controls: Add Pilote, Cancel, Add Trip
* Fields:
  * Title `text`
  * Dive Sites `search`
  * Date `text`
  * Starting time * `text`
  * Ending time * `text`
  * Max Capacity `number`
  * Instructor `search`
  * Description `textarea`
  * Description Activity Calendar `search`

### `trips`
* Columns: Title, Capacity, Pilot, Date
* Controls: Creation Date, delete Delete, edit Edit, Add Trip, Columns
* Fields:
  * Starting Date `text`

### `manager/products`
* Columns: Pos, Name, Activity Calendar, Sessions, Accommodation, Price
* Controls: NEW PRODUCT, Edit product categories, Columns, 25

### `settings/fee-management/new`
* Columns: Activity Calendar, Amount per hour, Amount per session, Commission per session %
* Controls: Add Activities to the Group, Cancel, Save
* Fields:
  * Enter name for fee group `text`
  * Validity Period `text`
  * To `text`

### `time-off`
* Columns: Staff, Time Off Starts, Time Off Ends, Note
* Controls: Add Time-Off, Columns, 10
* Fields:
  * Starting Date `text`
  * Instructor Instructor All MOSHIKO LEVY GIGI AMIR EDEN YUVAL VILENSKY INSTRU `select` — options: Instructor, All, MOSHIKO LEVY, GIGI AMIR, EDEN, YUVAL VILENSKY

### `unavailability-gear`
* Columns: Unit, Gear, Time Off Starts, Time Off Ends, Note
* Controls: ADD UNAVAILABILITY, Columns
* Fields:
  * Starting Date `text`

### `bookings/creditnote`
* Columns: ID, Name, Order, Creation Date, Total
* Controls: Refresh, Columns
* Fields:
  * Search client name Search booking code `text`

### `logs`
* Columns: Date, Staff, Log Type, Log Message
* Controls: Refresh, Columns, 10

### `manager/accommodations/new`
* Heading: ADD ACCOMMODATION
* Controls: Cancel, ADD ACCOMMODATION
* Fields:
  * Accommodation Name `text`
  * Input description `textarea`
  * Unit Name Units Quantity Maximum pax per unit `text`

### `manager/gears/new`
* Heading: Add Gear
* Controls: Cancel, Save
* Fields:
  * Gear Name `text`
  * Input description `textarea`
  * Unit Name Units Quantity Max Pax /Unit `text`

### `manager/promocode/new`
* Heading: Promo Code
* Controls: Fixed, Active, Cancel, SAVE
* Fields:
  * Title Promo Code info This is the sequence of character the customer will i `text`
  * Type (€/%) info Promo code can be a fixed amount (for ex : $10) or a percen `text`

### `report`
* Heading: Categories Revenue, Products Revenue
* Controls: keyboard_arrow_left, keyboard_arrow_right, file_download Export Bookings, file_download Export Invoices, file_download Export Payments, file_download Export Tickets
* Fields:
  * (unlabelled) `text`

### `booking/cart`
* Heading: ONLINE BOOKING Shokogi surf school, 1. Booking Summary, 2. Billing Information, 3. Validation & Payment
* Fields:
  * First Name * `text`
  * Last Name * `text`
  * +507Panama (Panamá)+507Afghanistan (‫افغانستان‬‎)+93Albania (Shqipëri)+355A `tel`
  * Email is Required! `text`
  * City is Required! `text`
  * Zip code is Required! `text`
  * Address `text`
  * Note `text`

### `manager/promocode`
* Columns: Title, Promo Code, Status, Value, Usage Count
* Controls: NEW PROMO CODE

### `manager/staff`
* Columns: Pos, Name, Role, Telephone, Hours this month
* Controls: NEW STAFF

### `settings/activity-settings/activity/new`
* Controls: Zoom in, Zoom out, Cancel, Save
* Fields:
  * Insert Name `text`
  * (unlabelled) `textarea`

### `settings/activity-settings/new`
* Controls: Zoom in, Zoom out, Cancel, Save
* Fields:
  * Insert Name `text`
  * (unlabelled) `textarea`

### `settings/integration/payments/paypal`
* Controls: Cancel, Confirm Payment Solution
* Fields:
  * Test Publishable Key `text`
  * ******** `password`
  * Live Publishable Key `text`

### `settings/integration/payments/six`
* Controls: Cancel, Confirm Payment Solution
* Fields:
  * Customer ID `text`
  * Terminal ID `text`
  * Username `text`
  * ******** `password`

### `settings/integration/payments/stripe`
* Controls: Cancel, Remove Payment Solution, Confirm Payment Solution
* Fields:
  * Live Publishable Key `text`
  * ******** `password`

### `commissions/new`
* Columns: Product Name
* Controls: ADD PRODUCTS TO THE GROUP, Cancel, Save
* Fields:
  * Enter Name for Commission Group `text`

### `partners`
* Columns: Partner Name, Commission Group, Telephone
* Controls: New Partner, Columns

### `settings/integration/management/i-calendar/new`
* Controls: Cancel, SAVE
* Fields:
  * Select staff to share `search`
  * Select activities to share `search`
  * Select participant custom fields to share `search`

### `settings/integration/payments/redsys`
* Controls: Cancel, Confirm Payment Solution
* Fields:
  * Merchant Number `text`
  * Terminal Number `text`
  * ******** `password`

### `settings/rules/new`
* Controls: Cancel, Save
* Fields:
  * Insert Name `text`
  * Date `text`

### `commissions`
* Columns: Name, Associated Partners
* Controls: New Commission Group, Columns

### `settings/custom-fields`
* Columns: Name, Label, Type
* Controls: New Field

### `settings/custom-fields/customer-form`
* Columns: Name, Label, Type
* Controls: New Field

### `settings/custom-fields/question-form`
* Columns: Name, Label, Type
* Controls: New Field

### `settings/general-settings/new`
* Controls: Cancel, Save
* Fields:
  * Payment Method Name `text`
  * Account number `text`

### `bookings/add`
* Controls: More, confirm 0.00 $, CANCEL

### `manager/products/create/init`
* Controls: Continue, Cancel

### `manager/products/create/setup`
* Controls: Continue, Cancel

### `manager/products/create`
* Controls: select

### `settings/e-commerce`
* Controls: Copy Code

### `booking`
* Heading: ONLINE BOOKING Shokogi surf school, 2 SURF LESSON 2024, Deals, 4 SURF LESSON 2024
* Controls: BOOK NOW

### `booking/reservation/participants`
* Heading: ONLINE BOOKING Shokogi surf school, 2 SURF LESSON 2024, Deals, 4 SURF LESSON 2024
* Controls: BOOK NOW

### `booking/reservation/sessions`
* Heading: ONLINE BOOKING Shokogi surf school, 2 SURF LESSON 2024, Deals, 4 SURF LESSON 2024
* Controls: BOOK NOW

## String groups

Where the crawler saw nothing, these are the labels the feature uses.

* **label** — 248 strings
* **bookings** — 181 strings
* **products** — 125 strings
* **fields** — 120 strings
* **minisite** — 77 strings
* **agenda** — 67 strings
* **sessions** — 66 strings
* **actions** — 62 strings
* **report** — 56 strings
* **fiscal** — 39 strings
* **promocode** — 39 strings
* **trip** — 37 strings
* **client_documents** — 24 strings
* **custom_fields** — 24 strings
* **fees_management** — 24 strings
* **home** — 24 strings
* **icalendar** — 24 strings
* **pricing** — 21 strings
* **time_off** — 20 strings
* **accommodations** — 19 strings
* **errors** — 18 strings
* **pos** — 18 strings
* **partner** — 17 strings
* **auth** — 15 strings
* **messages** — 15 strings
* **selects** — 14 strings
* **buttons** — 13 strings
* **fees_groups** — 13 strings
* **profile** — 12 strings
* **settings** — 12 strings
* **payment** — 11 strings
* **success** — 9 strings
* **commission_groups** — 8 strings
* **customer** — 8 strings
* **staff** — 8 strings
* **tax_notes** — 8 strings
