// ============================================================
// STATION MÉTÉO AGRICOLE 
// ESP32 + WiFi (prioritaire) + SIM7600E 4G (fallback hors ligne)
// GPS intégré + DHT11 + ZTS-3000 + Humidité sol
//
// LOGIQUE DE CONNEXION :
//   1. Tente WiFi au démarrage (5 secondes)
//   2. Si WiFi absent → bascule 4G via SIM7600E automatiquement
//   3. À chaque cycle, re-vérifie WiFi d'abord (si revenu)
//   4. GPS lu à chaque cycle → coordonnées dans chaque mesure
// ============================================================

#include <WiFi.h>
#include <HTTPClient.h>
#include <HardwareSerial.h>
#include <DHT.h>
#include <time.h>

// ============================================================
// ⚙️  CONFIGURATION 
// ============================================================
#define WIFI_SSID       "Ussein_LS"
#define WIFI_PASSWORD   "Ussein@12345"

#define FIREBASE_HOST   "stationmeteo-3dc5d-default-rtdb.firebaseio.com"
#define FIREBASE_AUTH   "HcyeDjz44M6TUw5MmLVqnxHMIsbay6a3KfxoyooO"
#define STATION_ID      "ST002"

#define APN             "orange.sn"   // Orange Sénégal — changer si autre opérateur
// ============================================================

// --- Broches capteurs ---
#define DHT_PIN         4
#define DHT_TYPE        DHT11
#define ANEMOMETRE_PIN  18
#define SOL_PIN         35
// --- Calibration capteurs ---
#define FACTEUR_VENT    0.667   // ZTS-3000 : 1 Hz = 0.667 m/s

// --- Broches SIM7600E ---
#define SIM_RX_PIN      26
#define SIM_TX_PIN      27
#define SIM_BAUDRATE    115200

// --- Timing ---
#define WIFI_TIMEOUT_MS  5000   // 5s max pour connexion WiFi

// ── Heures d'envoi (3 fois par jour comme une météo normale) ──
// Format 24h — modifiez ces 3 valeurs pour changer les horaires
#define HEURE_MATIN   6    // 06:00 — relevé du matin (Sol frais, avant chaleur)
#define HEURE_MIDI    12   // 12:00 — relevé de midi (Point chaud de la journée)
#define HEURE_SOIR    19   // 18:00 — relevé du soir (Fin de journée, bilan)
// Tolérance : envoi déclenché dans la minute qui suit l'heure pile
#define TOLERANCE_MIN  1   // minute(s) de tolérance

// ============================================================
// LIMITES PHYSIQUES (filtre de seuil)
// ============================================================
#define TEMP_MIN        10.0
#define TEMP_MAX        50.0
#define HUM_AIR_MIN     10.0
#define HUM_AIR_MAX     100.0
#define HUM_SOL_MIN     0.0
#define HUM_SOL_MAX     100.0
#define VENT_MAX_KMH    60.0

// ============================================================
// MOYENNE GLISSANTE (fenêtre de 5 mesures)
// ============================================================
#define NB_MESURES 5

float histTemp[NB_MESURES]   = {0,0,0,0,0};
float histHumAir[NB_MESURES] = {0,0,0,0,0};
float histHumSol[NB_MESURES] = {0,0,0,0,0};
float histVent[NB_MESURES]   = {0,0,0,0,0};
int idxTemp=0, idxHumAir=0, idxHumSol=0, idxVent=0;
int nbTemp=0,  nbHumAir=0,  nbHumSol=0,  nbVent=0;

// ============================================================
// VARIABLES GLOBALES
// ============================================================
DHT dht(DHT_PIN, DHT_TYPE);
HardwareSerial simSerial(1);

volatile unsigned long compteur = 0;
unsigned long dernierCalcul     = 0;
unsigned long dernierEnvoi      = 0;
// Empêcher l'envoi du premier cycle (vent non initialisé)
bool premierCycleIgnore = false;

// Heure du dernier envoi (évite double envoi dans la même minute)
int  dernierEnvoiHeure  = -1;   // heure (0-23) du dernier envoi
int  dernierEnvoiMinute = -1;   // minute du dernier envoi

// Mode de connexion actif
typedef enum { MODE_WIFI, MODE_4G, MODE_AUCUN } ModeConnexion;
ModeConnexion modeActif = MODE_AUCUN;

// GPS
float gpsLatitude  = 0.0;
float gpsLongitude = 0.0;
float gpsAltitude  = 0.0;
bool  gpsFixOk     = false;

// SIM7600 prêt
bool sim4GReady = false;


// ============================================================
// INTERRUPTION anémomètre ZTS-3000 NPN
// ============================================================
void IRAM_ATTR onImpulsion() {
  compteur++;
}


// ============================================================
// FILTRAGE — seuil + moyenne glissante (identique au code v1)
// ============================================================
float filtrerValeur(float valeur, float valMin, float valMax,
                    float* historique, int &index, int &nbValides,
                    const char* nom) {
  // Filtre de seuil
  if (isnan(valeur) || valeur < valMin || valeur > valMax) {
    Serial.printf("[FILTRE] Parasite %s : %.2f\n", nom, valeur);
    if (nbValides == 0) return (valMin + valMax) / 2.0;
    float s = 0;
    int n = min(nbValides, NB_MESURES);
    for (int i = 0; i < n; i++) s += historique[i];
    return s / n;
  }
  // Moyenne glissante
  historique[index] = valeur;
  index = (index + 1) % NB_MESURES;
  if (nbValides < NB_MESURES) nbValides++;
  float s = 0;
  int n = min(nbValides, NB_MESURES);
  for (int i = 0; i < n; i++) s += historique[i];
  return s / n;
}


// ============================================================
// LECTURE CAPTEURS
// ============================================================
float lireTemperature() {
  return filtrerValeur(dht.readTemperature(), TEMP_MIN, TEMP_MAX,
                       histTemp, idxTemp, nbTemp, "Temp");
}
float lireHumiditeAir() {
  return filtrerValeur(dht.readHumidity(), HUM_AIR_MIN, HUM_AIR_MAX,
                       histHumAir, idxHumAir, nbHumAir, "HumAir");
}
float lireHumiditeSol() {
  int raw = analogRead(SOL_PIN);
  float brut = constrain(map(raw, 4095, 1500, 0, 100), 0, 100);
  return filtrerValeur(brut, HUM_SOL_MIN, HUM_SOL_MAX,
                       histHumSol, idxHumSol, nbHumSol, "HumSol");
}
float lireVitesseVent() {
  unsigned long maintenant = millis();
  unsigned long duree = maintenant - dernierCalcul;
  
  noInterrupts();
  unsigned long imp = compteur;
  compteur = 0;
  interrupts();
  
  dernierCalcul = maintenant;

  // Initialiser dernierCalcul au premier appel
  static bool premierAppel = true;
  if (premierAppel) {
    premierAppel = false;
    dernierCalcul = maintenant;
    noInterrupts();
    compteur = 0;  // remettre à zéro proprement
    interrupts();
    Serial.println("   [Vent] Premier appel — compteur réinitialisé");
    return 0.0;  // retourner 0 uniquement ce premier appel
  }

  if (duree < 1000) return 0.0;

  float hz  = (float)imp / (duree / 1000.0);
  float kmh = hz * FACTEUR_VENT * 3.6;

  Serial.printf("   [Vent] imp:%lu duree:%lums hz:%.2f kmh:%.2f\n",
                imp, duree, hz, kmh);

  return filtrerValeur(kmh, 0.0, VENT_MAX_KMH,
                       histVent, idxVent, nbVent, "Vent");
}


// ============================================================
// TIMESTAMP NTP (WiFi uniquement)
// ============================================================
String obtenirTimestamp() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    return "inconnu_" + String(millis());
  }
  char buf[25];
  strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &timeinfo);
  return String(buf);
}


// ============================================================
// CONSTRUCTION DU JSON (partagé WiFi + 4G)
// ============================================================
String construireJSON(float temp, float humAir,
                      float vent, float humSol,
                      String timestamp) {
  String json = "{";
  json += "\"temperature\":"  + String(temp,          2) + ",";
  json += "\"humidite_air\":" + String(humAir,        2) + ",";
  json += "\"vitesse_vent\":" + String(vent,           2) + ",";
  json += "\"humidite_sol\":" + String(humSol,         2) + ",";
  json += "\"station_id\":\""  + String(STATION_ID)  + "\",";
  json += "\"latitude\":"     + String(gpsLatitude,   6) + ",";
  json += "\"longitude\":"    + String(gpsLongitude,  6) + ",";
  json += "\"gps_fix\":"      + String(gpsFixOk ? "true" : "false") + ",";
  json += "\"timestamp\":\""  + timestamp             + "\"";
  json += "}";
  return json;
}


// ============================================================
// ENVOI FIREBASE — MODE WIFI
// ============================================================
void envoyerFirebaseWiFi(float temp, float humAir,
                          float vent, float humSol) {
  if (WiFi.status() != WL_CONNECTED) return;

  String ts   = obtenirTimestamp();
  String json = construireJSON(temp, humAir, vent, humSol, ts);
  HTTPClient http;

  // PUT → mesures actuelles (écrasées à chaque cycle)
  String urlMesures = "https://" + String(FIREBASE_HOST)
                    + "/stations/" + STATION_ID + "/mesures.json"
                    + "?auth=" + FIREBASE_AUTH;
  http.begin(urlMesures);
  http.addHeader("Content-Type", "application/json");
  int code = http.PUT(json);
  Serial.println("[WiFi] PUT mesures → HTTP " + String(code));
  http.end();

  // POST → historique (nouvelle entrée permanente)
  String urlHisto = "https://" + String(FIREBASE_HOST)
                  + "/stations/" + STATION_ID + "/historique.json"
                  + "?auth=" + FIREBASE_AUTH;
  http.begin(urlHisto);
  http.addHeader("Content-Type", "application/json");
  code = http.POST(json);
  Serial.println("[WiFi] POST historique → HTTP " + String(code));
  http.end();

  // PUT → GPS séparé (nœud dédié pour la carte admin)
  if (gpsFixOk) {
    String urlGPS = "https://" + String(FIREBASE_HOST)
                  + "/stations/" + STATION_ID + "/gps.json"
                  + "?auth=" + FIREBASE_AUTH;
    String jsonGPS = "{\"latitude\":" + String(gpsLatitude, 6)
                   + ",\"longitude\":" + String(gpsLongitude, 6)
                   + ",\"altitude\":" + String(gpsAltitude, 1)
                   + ",\"timestamp\":\"" + ts + "\"}";
    http.begin(urlGPS);
    http.addHeader("Content-Type", "application/json");
    http.PUT(jsonGPS);
    http.end();
    Serial.println("[WiFi] GPS sauvegardé dans Firebase");
  }
  // ── Déclencher le calcul de recommandation SMS sur le backend ──
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient httpSms;
    String urlSms = "https://agri-station-meteo.onrender.com/sms/recommandation/" + String(STATION_ID);
    httpSms.begin(urlSms);
    int codeSms = httpSms.GET();
    Serial.println("[WiFi] Recommandation SMS → HTTP " + String(codeSms));
    httpSms.end();
  }
}


// ============================================================
// COMMANDES AT — SIM7600E
// ============================================================
String envoyerAT(String cmd, int timeout_ms = 3000) {
  while (simSerial.available()) simSerial.read();
  simSerial.println(cmd);
  String rep = "";
  unsigned long t = millis();
  while (millis() - t < timeout_ms) {
    while (simSerial.available()) rep += (char)simSerial.read();
  }
  Serial.print("[AT] " + cmd.substring(0, 30) + " → ");
  Serial.println(rep.length() > 80 ? rep.substring(0, 80) + "..." : rep);
  return rep;
}

bool attendreReponse(String motCle, int timeout_ms = 10000) {
  String rep = "";
  unsigned long t = millis();
  while (millis() - t < timeout_ms) {
    while (simSerial.available()) {
      rep += (char)simSerial.read();
      if (rep.indexOf(motCle) != -1) return true;
    }
  }
  Serial.println("[TIMEOUT] Attendu : " + motCle);
  return false;
}

// Heure réseau opérateur via SIM7600E (disponible sans NTP)
String obtenirTimestamp4G() {
  String rep = envoyerAT("AT+CCLK?", 3000);
  // Réponse : +CCLK: "26/06/04,23:30:00+00"
  int debut = rep.indexOf("\"");
  int fin   = rep.lastIndexOf("\"");
  if (debut == -1 || fin <= debut) {
    return "offline_" + String(millis() / 1000) + "s";
  }
  String cclk = rep.substring(debut + 1, fin);
  // Convertir "26/06/04,23:30:00+00" → "2026-06-04 23:30:00"
  if (cclk.length() < 17) return "offline_" + String(millis() / 1000) + "s";
  String ts = "20" + cclk.substring(0, 2)   // année
            + "-" + cclk.substring(3, 5)     // mois
            + "-" + cclk.substring(6, 8)     // jour
            + " " + cclk.substring(9, 17);   // heure
  return ts;
}
// ============================================================
// INITIALISATION SIM7600E + 4G
// ============================================================
bool initSIM7600() {
  Serial.println("\n=== Init SIM7600E ===");

  // Reset logiciel si le module est bloqué
  envoyerAT("AT+HTTPTERM", 2000);
  delay(500);
  envoyerAT("AT+CGACT=0,1", 3000);
  delay(500);

  bool repond = false;
  for (int i = 0; i < 8; i++) {
    if (envoyerAT("AT", 1500).indexOf("OK") != -1) { repond = true; break; }
    Serial.print(".");
    delay(2000);
  }
  if (!repond) {
    // Dernier recours — reset matériel logiciel
    Serial.println("[SIM] Reset AT+CFUN=1,1...");
    simSerial.println("AT+CFUN=1,1");
    delay(8000);
    for (int i = 0; i < 6; i++) {
      if (envoyerAT("AT", 1500).indexOf("OK") != -1) { repond = true; break; }
      delay(2000);
    }
  }
  if (!repond) { Serial.println("SIM7600E ne répond pas"); return false; }

  envoyerAT("ATE0");
  envoyerAT("AT+CMEE=2");

  String imsi = envoyerAT("AT+CIMI", 3000);
  if (imsi.indexOf("ERROR") != -1 || imsi.length() < 12) {
    Serial.println("Pas de SIM détectée !"); return false;
  }

  Serial.print("Recherche réseau 4G");
  for (int i = 0; i < 20; i++) {
    String creg = envoyerAT("AT+CREG?", 2000);
    if (creg.indexOf(",1") != -1 || creg.indexOf(",5") != -1) {
      Serial.println(" OK");
      break;
    }
    if (i == 19) { Serial.println(" ECHEC"); return false; }
    Serial.print(".");
    delay(3000);
  }

  envoyerAT("AT+CNMP=38", 2000);   // LTE uniquement
  delay(500);
  envoyerAT("AT+CGDCONT=1,\"IP\",\"" + String(APN) + "\"", 3000);
  delay(500);
  envoyerAT("AT+CGACT=1,1", 10000);
  delay(2000);

  // ── Synchronisation horloge réseau ──────────────────────────
  envoyerAT("AT+CTZU=1", 2000);    // sync auto horloge via réseau
  delay(3000);                      // attendre la sync
  Serial.println("[TIME] " + envoyerAT("AT+CCLK?", 2000));  // vérifier

  String ip = envoyerAT("AT+CGPADDR=1", 3000);
  if (ip.indexOf("0.0.0.0") != -1 || ip.indexOf("ERROR") != -1) {
    Serial.println("IP non obtenue"); return false;
  }
  Serial.println("=== SIM7600E prêt — IP : " + ip);
  return true;
}


// ============================================================
// ENVOI FIREBASE — MODE 4G (SIM7600E)
// ============================================================
bool envoyerFirebase4G(float temp, float humAir,
                       float vent, float humSol) {

  String ts   = obtenirTimestamp4G();
  String json = construireJSON(temp, humAir, vent, humSol, ts);
  Serial.println("[4G] JSON : " + json);

  // ── Firebase direct (Render abandonné — cold start >60s impossible depuis SIM) ──
  // POST  → historique.json   : crée une entrée (clé push Firebase) ✅ confirmé
  // POST+override → mesures.json : SET les mesures temps réel

  // ── 1. HISTORIQUE ─────────────────────────────────────────────────────────
  bool okHisto = false;
  {
    envoyerAT("AT+HTTPTERM", 1000); delay(500);
    if (envoyerAT("AT+HTTPINIT", 5000).indexOf("OK") != -1) {
      String url = "https://" + String(FIREBASE_HOST)
                 + "/stations/" + STATION_ID + "/historique.json"
                 + "?auth=" + String(FIREBASE_AUTH);
      envoyerAT("AT+HTTPPARA=\"URL\",\"" + url + "\"", 3000);
      envoyerAT("AT+HTTPPARA=\"CONTENT\",\"application/json\"", 3000);

      simSerial.println("AT+HTTPDATA=" + String(json.length()) + ",10000");
      if (attendreReponse("DOWNLOAD", 8000)) {
        simSerial.print(json); delay(2000);
        simSerial.println("AT+HTTPACTION=1");  // POST
        String rep = ""; unsigned long t = millis();
        while (millis() - t < 15000) {
          while (simSerial.available()) rep += (char)simSerial.read();
          if (rep.indexOf("+HTTPACTION") != -1) break;
          if (rep.indexOf("ERROR")       != -1) break;
        }
        okHisto = rep.indexOf(",200,") != -1 || rep.indexOf(",201,") != -1;
        Serial.println("[4G] POST historique : " + String(okHisto ? "OK ✅" : "ECHEC") + " | " + rep.substring(0,40));
      }
      envoyerAT("AT+HTTPTERM", 2000);
    }
  }

  // ── 2. MESURES (temps réel) ───────────────────────────────────────────────
  bool okMesures = false;
  {
    delay(500);
    envoyerAT("AT+HTTPTERM", 1000); delay(500);
    if (envoyerAT("AT+HTTPINIT", 5000).indexOf("OK") != -1) {
      String url = "https://" + String(FIREBASE_HOST)
                 + "/stations/" + STATION_ID + "/mesures.json"
                 + "?auth=" + String(FIREBASE_AUTH);
      envoyerAT("AT+HTTPPARA=\"URL\",\"" + url + "\"", 3000);
      envoyerAT("AT+HTTPPARA=\"CONTENT\",\"application/json\"", 3000);
      envoyerAT("AT+HTTPPARA=\"USERDATA\",\"X-HTTP-Method-Override: PUT\"", 2000);

      simSerial.println("AT+HTTPDATA=" + String(json.length()) + ",10000");
      if (attendreReponse("DOWNLOAD", 8000)) {
        simSerial.print(json); delay(2000);
        simSerial.println("AT+HTTPACTION=1");  // POST → Firebase honore Override: PUT
        String rep = ""; unsigned long t = millis();
        while (millis() - t < 15000) {
          while (simSerial.available()) rep += (char)simSerial.read();
          if (rep.indexOf("+HTTPACTION") != -1) break;
          if (rep.indexOf("ERROR")       != -1) break;
        }
        okMesures = rep.indexOf(",200,") != -1;
        Serial.println("[4G] SET mesures : " + String(okMesures ? "OK ✅" : "ECHEC") + " | " + rep.substring(0,40));
      }
      envoyerAT("AT+HTTPTERM", 2000);
    }
  }

  // ── 3. GPS (si fix disponible) ────────────────────────────────────────────
  if (gpsFixOk) {
    delay(500);
    envoyerAT("AT+HTTPTERM", 1000); delay(500);
    if (envoyerAT("AT+HTTPINIT", 5000).indexOf("OK") != -1) {
      String urlGPS = "https://" + String(FIREBASE_HOST)
                    + "/stations/" + STATION_ID + "/gps.json"
                    + "?auth=" + String(FIREBASE_AUTH);
      String jsonGPS = "{\"latitude\":"  + String(gpsLatitude,  6)
                     + ",\"longitude\":" + String(gpsLongitude, 6)
                     + ",\"altitude\":"  + String(gpsAltitude,  1)
                     + ",\"timestamp\":\"" + ts + "\"}";

      envoyerAT("AT+HTTPPARA=\"URL\",\"" + urlGPS + "\"", 3000);
      envoyerAT("AT+HTTPPARA=\"CONTENT\",\"application/json\"", 3000);
      envoyerAT("AT+HTTPPARA=\"USERDATA\",\"X-HTTP-Method-Override: PUT\"", 2000);

      simSerial.println("AT+HTTPDATA=" + String(jsonGPS.length()) + ",10000");
      if (attendreReponse("DOWNLOAD", 8000)) {
        simSerial.print(jsonGPS); delay(2000);
        simSerial.println("AT+HTTPACTION=1");
        delay(8000);
        Serial.println("[4G] SET gps ✅");
      }
      envoyerAT("AT+HTTPTERM", 2000);
    }
  }

  return okHisto || okMesures;
}






// ============================================================
// GPS — INITIALISATION
// ============================================================
void initGPS() {
  Serial.println("[GPS] Activation...");

  // Essai 1 — commande sans paramètre (Waveshare SIM7600E)
  String rep = envoyerAT("AT+CGPS=1", 5000);
  if (rep.indexOf("OK") != -1) {
    Serial.println("[GPS] Activé avec succès");
    return;
  }

  // Essai 2 — éteindre puis rallumer
  envoyerAT("AT+CGPS=0", 2000);
  delay(1000);
  rep = envoyerAT("AT+CGPS=1", 5000);
  if (rep.indexOf("OK") != -1) {
    Serial.println("[GPS] Activé après reset");
    return;
  }

  // Essai 3 — commande avec paramètre
  rep = envoyerAT("AT+CGPS=1,1", 5000);
  if (rep.indexOf("OK") != -1) {
    Serial.println("[GPS] Activé (mode 1,1)");
    return;
  }

  Serial.println("[GPS] Avertissement — GPS non activé, continue sans GPS");
}


// ============================================================
// GPS — LECTURE
// ============================================================
bool lireGPS() {
  String rep = envoyerAT("AT+CGPSINFO", 5000);

  if (rep.indexOf("+CGPSINFO:") == -1 || rep.indexOf(",,,,,,,,") != -1) {
    Serial.println("[GPS] Pas encore de fix...");
    gpsFixOk = false;
    return false;
  }

  int debut = rep.indexOf("+CGPSINFO:") + 11;
  String info = rep.substring(debut);
  info.trim();

  // Parse NMEA : DDMM.MMMM,N,DDDMM.MMMM,E,...
  String champs[9];
  int idx = 0;
  for (int i = 0; i < (int)info.length() && idx < 9; i++) {
    if (info[i] == ',') idx++;
    else if (idx < 9) champs[idx] += info[i];
  }

  if (champs[0].length() < 4) { gpsFixOk = false; return false; }

  // Latitude
  float latRaw = champs[0].toFloat();
  int   latDeg = (int)(latRaw / 100);
  gpsLatitude  = latDeg + (latRaw - latDeg * 100) / 60.0;
  if (champs[1] == "S") gpsLatitude = -gpsLatitude;

  // Longitude
  float lonRaw = champs[2].toFloat();
  int   lonDeg = (int)(lonRaw / 100);
  gpsLongitude = lonDeg + (lonRaw - lonDeg * 100) / 60.0;
  if (champs[3] == "W") gpsLongitude = -gpsLongitude;

  gpsAltitude = champs[6].toFloat();
  gpsFixOk    = true;

  Serial.printf("[GPS] Fix OK → %.6f, %.6f (alt %.1fm)\n",
                gpsLatitude, gpsLongitude, gpsAltitude);
  return true;
}


// ============================================================
// TENTATIVE CONNEXION WIFI
// ============================================================
bool connecterWiFi() {
  if (WiFi.status() == WL_CONNECTED) return true;

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[WiFi] Connexion");
  unsigned long t = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t < WIFI_TIMEOUT_MS) {
    delay(250);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println(" OK → " + WiFi.localIP().toString());
    return true;
  }
  Serial.println(" ABSENT");
  WiFi.disconnect();
  return false;
}



// ============================================================
// VÉRIFICATION HEURE D'ENVOI (matin / midi / soir)
// ============================================================
// Retourne true UNE SEULE FOIS par créneau horaire.
// La tolérance TOLERANCE_MIN permet de ne pas rater l'heure
// si le loop() tourne toutes les 60 secondes.
// ============================================================
bool estHeureEnvoi() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    // NTP non sync (mode 4G hors WiFi) — on utilise un timer de secours
    // Envoi toutes les 6 heures en mode dégradé
    static unsigned long dernierSecours = 0;
    if (millis() - dernierSecours >= 6UL * 3600UL * 1000UL) {
      dernierSecours = millis();
      Serial.println("[TIMING] Mode dégradé — NTP absent, envoi de secours");
      return true;
    }
    return false;
  }

  int heure  = timeinfo.tm_hour;
  int minute = timeinfo.tm_min;

  // Vérifier si c'est l'un des 3 créneaux ET si on n'a pas déjà envoyé
  bool creneau = (heure == HEURE_MATIN || heure == HEURE_MIDI || heure == HEURE_SOIR)
                 && minute < TOLERANCE_MIN;

  if (!creneau) return false;

  // Éviter le double envoi dans la même minute
  if (heure == dernierEnvoiHeure && minute == dernierEnvoiMinute) return false;

  // Enregistrer ce créneau comme traité
  dernierEnvoiHeure  = heure;
  dernierEnvoiMinute = minute;

  String nomCreneau = (heure == HEURE_MATIN) ? "MATIN" :
                      (heure == HEURE_MIDI)  ? "MIDI"  : "SOIR";
  Serial.println("[TIMING] Créneau " + nomCreneau
               + " — " + String(heure) + "h" + String(minute));
  return true;
}


// ============================================================
// SETUP
// ============================================================
void setup() {
  Serial.begin(115200);
  delay(1500);

  Serial.println("\n================================");
  Serial.println("  Station Meteo Agricole v3.0");
  Serial.println("  ESP32 + WiFi + SIM7600E 4G");
  Serial.println("================================\n");

  // Capteurs
  dht.begin();
  pinMode(ANEMOMETRE_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(ANEMOMETRE_PIN), onImpulsion, FALLING);
  Serial.println("[OK] DHT11 + Anémomètre + Sol");

  // SIM7600E — toujours initialisé (même si WiFi disponible)
  // car on a besoin du GPS même en mode WiFi
  simSerial.begin(SIM_BAUDRATE, SERIAL_8N1, SIM_RX_PIN, SIM_TX_PIN);
  delay(3000);
  Serial.println("[OK] UART SIM7600E GPIO" + String(SIM_RX_PIN) + "/" + String(SIM_TX_PIN));

  for (int tentative = 1; tentative <= 3; tentative++) {
    Serial.println("Tentative SIM7600E " + String(tentative) + "/3...");
    sim4GReady = initSIM7600();
    if (sim4GReady) break;
    delay(5000);
  }

  if (!sim4GReady) {
    Serial.println("[WARN] SIM7600E non dispo — mode WiFi uniquement");
  } else {
    // GPS uniquement si SIM7600E est prêt
    initGPS();
  }
  
  // Tente WiFi
  bool wifiOk = connecterWiFi();
  if (wifiOk) {
    // NTP uniquement si WiFi dispo
    configTime(0, 0, "pool.ntp.org", "time.nist.gov");
    setenv("TZ", "GMT0", 1);
    tzset();
    Serial.print("[NTP] Sync");
    struct tm ti;
    for (int i = 0; i < 20 && !getLocalTime(&ti); i++) {
      delay(500); Serial.print(".");
    }
    Serial.println(" OK → " + obtenirTimestamp());
    modeActif = MODE_WIFI;
  } else if (sim4GReady) {
    modeActif = MODE_4G;
  } else {
    modeActif = MODE_AUCUN;
    Serial.println("[WARN] Aucune connexion disponible !");
  }

  // Initialiser le compteur vent proprement
  noInterrupts();
  compteur = 0;
  interrupts();
  dernierCalcul = millis();
  dernierEnvoi  = millis();

  Serial.println("\n[OK] Système prêt — mode : " + String(
    modeActif == MODE_WIFI ? "WiFi" :
    modeActif == MODE_4G   ? "4G"   : "AUCUN"
  ) + "\n");
}

// ============================================================
// LECTURE SMS DEPUIS FIREBASE ET ENVOI VIA SIM7600E
// ============================================================
bool lireSmsAEnvoyer(String &message, String &telephone) {
  // ─── GET /stations/ST002/sms_a_envoyer.json ───────────────────────────
  envoyerAT("AT+HTTPTERM", 1000);
  delay(500);
  if (envoyerAT("AT+HTTPINIT", 5000).indexOf("OK") == -1) {
    Serial.println("[SMS] HTTPINIT echoue");
    return false;
  }

  String url = "https://" + String(FIREBASE_HOST)
             + "/stations/" + STATION_ID + "/sms_a_envoyer.json"
             + "?auth=" + String(FIREBASE_AUTH);

  envoyerAT("AT+HTTPPARA=\"URL\",\"" + url + "\"", 3000);

  while (simSerial.available()) simSerial.read();
  simSerial.println("AT+HTTPACTION=0");

  String repAction = "";
  unsigned long t = millis();
  while (millis() - t < 20000) {
    while (simSerial.available()) repAction += (char)simSerial.read();
    if (repAction.indexOf("+HTTPACTION") != -1) break;
  }
  Serial.println("[SMS] HTTPACTION : " + repAction);

  if (repAction.indexOf("200") == -1) {
    Serial.println("[SMS] Erreur HTTP GET Firebase");
    envoyerAT("AT+HTTPTERM");
    return false;
  }

  // ── Taille du body depuis "+HTTPACTION: 0,200,270" ────────────────────
  int dataLen = 0;
  {
    int lastComma = repAction.lastIndexOf(",");
    if (lastComma != -1) {
      String lenStr = repAction.substring(lastComma + 1);
      lenStr.trim();
      dataLen = lenStr.toInt();
    }
  }
  Serial.println("[SMS] Taille body : " + String(dataLen) + " octets");

  // ── Lire le body JSON ─────────────────────────────────────────────────
  // IMPORTANT : AT+HTTPREAD=0,N renvoie d'abord \r\nOK\r\n AVANT les données
  // sous forme +HTTPREAD: DATA,N\r\n<json>\r\nOK
  // → ne pas s'arrêter sur le premier OK, attendre le marqueur DATA.
  delay(300);
  while (simSerial.available()) simSerial.read();

  if (dataLen > 0) {
    simSerial.println("AT+HTTPREAD=0," + String(dataLen));
  } else {
    simSerial.println("AT+HTTPREAD");
  }

  String raw = "";
  t = millis();
  while (millis() - t < 12000) {
    while (simSerial.available()) raw += (char)simSerial.read();
    // Attendre que le marqueur DATA soit présent
    int dataMarker = raw.indexOf("+HTTPREAD: DATA");
    if (dataMarker != -1) {
      int jsonStart = raw.indexOf("\r\n", dataMarker) + 2;
      if (jsonStart > 1) {
        int bytesApresHeader = (int)raw.length() - jsonStart;
        // Arrêt dès qu'on a tous les octets attendus
        if (dataLen > 0 && bytesApresHeader >= dataLen) break;
        // Ou dès que le JSON est fermé (})
        if (raw.lastIndexOf("}") > jsonStart) break;
      }
    }
    if (raw.indexOf("ERROR") != -1) break;
  }

  // ── Extraire uniquement la partie JSON (après le marqueur DATA) ────────
  String body = raw;
  int dataMarker = raw.indexOf("+HTTPREAD: DATA");
  if (dataMarker != -1) {
    int jsonStart = raw.indexOf("\r\n", dataMarker) + 2;
    if (jsonStart > 1) {
      body = raw.substring(jsonStart);
      // Supprimer le \r\nOK final s'il est présent
      int trailOk = body.lastIndexOf("\r\nOK");
      if (trailOk != -1) body = body.substring(0, trailOk);
    }
  }

  Serial.println("[SMS] Body JSON (" + String(body.length()) + ") : " + body.substring(0, 100));
  envoyerAT("AT+HTTPTERM");

  // ─── Vérifier si un SMS est EN ATTENTE (envoye = false) ───────────────
  bool smsEnAttente = (body.indexOf("\"envoye\":false")  != -1)
                   || (body.indexOf("\"envoye\": false") != -1);
  if (!smsEnAttente) {
    Serial.println("[SMS] Aucun SMS en attente");
    return false;
  }

  // ─── Parser le message ─────────────────────────────────────────────────
  int idxMsg = body.indexOf("\"message\":\"");
  if (idxMsg != -1) {
    int debut = idxMsg + 11;
    // Chercher le " fermant en sautant les \" échappés
    int fin = debut;
    while (true) {
      fin = body.indexOf("\"", fin);
      if (fin == -1) break;               // pas trouvé
      if (body.charAt(fin - 1) != '\\') break;  // vrai guillemet fermant
      fin++;                              // guillemet échappé → continuer
    }
    if (fin > debut) {
      message = body.substring(debut, fin);
      message.replace("\\n", "\n");
      message.replace("\\u2014", "-");   // tiret long —
      message.replace("\\u00e9", "e");   // é
      message.replace("\\u00e0", "a");   // à
      message.replace("\\u00e8", "e");   // è
    }
  }

  // ─── Parser le téléphone ───────────────────────────────────────────────
  int idxTel = body.indexOf("\"telephone\":\"");
  if (idxTel != -1) {
    int debut = idxTel + 13;
    int fin   = body.indexOf("\"", debut);
    if (fin > debut) telephone = body.substring(debut, fin);
  }

  Serial.println("[SMS] Message  : " + message.substring(0, 80));
  Serial.println("[SMS] Telephone: " + telephone);

  return (message.length() > 0 && telephone.length() > 0);
}

void envoyerSMS(String telephone, String message) {
  Serial.println("[SMS] Envoi → " + telephone);
  Serial.println("[SMS] Message : " + message.substring(0, 80));

  // ── Vérifier l'enregistrement réseau ────────────────────────────────────
  String creg = envoyerAT("AT+CREG?", 2000);
  if (creg.indexOf(",1") == -1 && creg.indexOf(",5") == -1) {
    Serial.println("[SMS] Module non enregistre reseau — SMS annule");
    return;
  }
  // Attendre 3s pour que le service SMS soit stable après un éventuel reinit
  delay(3000);

  // Mode texte
  while (simSerial.available()) simSerial.read();  // vider le buffer
  envoyerAT("AT+CMGF=1", 2000);
  delay(500);

  // Format international
  String numTel = telephone;
  if (!numTel.startsWith("+") && !numTel.startsWith("00")) {
    numTel = "+221" + numTel;
  }
  Serial.println("[SMS] Numero : " + numTel);

  // ── Nettoyage UTF-8 → ASCII pur ─────────────────────────────────────────
  String msgPropre = "";
  int mLen = (int)message.length();
  for (int i = 0; i < mLen; ) {
    unsigned char c = (unsigned char)message.charAt(i);
    if (c == 0xE2 && i + 2 < mLen) {
      unsigned char c2 = (unsigned char)message.charAt(i+1);
      unsigned char c3 = (unsigned char)message.charAt(i+2);
      if (c2 == 0x80) {
        if      (c3==0x94||c3==0x93)          { msgPropre+='-'; }
        else if (c3==0x99||c3==0x98)          { msgPropre+='\''; }
        else if (c3==0x9C||c3==0x9D)          { msgPropre+='"'; }
        else if (c3==0xA6)                    { msgPropre+='.'; }
      }
      i+=3; continue;
    }
    if (c == 0xC3 && i + 1 < mLen) {
      unsigned char c2 = (unsigned char)message.charAt(i+1);
      switch(c2){
        case 0xA0:case 0xA1:case 0xA2:case 0xA3:case 0xA4:case 0xA5: msgPropre+='a';break;
        case 0xA7: msgPropre+='c'; break;
        case 0xA8:case 0xA9:case 0xAA:case 0xAB: msgPropre+='e'; break;
        case 0xAC:case 0xAD:case 0xAE:case 0xAF: msgPropre+='i'; break;
        case 0xB1: msgPropre+='n'; break;
        case 0xB2:case 0xB3:case 0xB4:case 0xB5:case 0xB6: msgPropre+='o'; break;
        case 0xB9:case 0xBA:case 0xBB:case 0xBC: msgPropre+='u'; break;
        case 0x80:case 0x81:case 0x82:case 0x83:case 0x84:case 0x85: msgPropre+='A';break;
        case 0x87: msgPropre+='C'; break;
        case 0x88:case 0x89:case 0x8A:case 0x8B: msgPropre+='E'; break;
        case 0x8C:case 0x8D:case 0x8E:case 0x8F: msgPropre+='I'; break;
        case 0x91: msgPropre+='N'; break;
        case 0x92:case 0x93:case 0x94:case 0x95:case 0x96: msgPropre+='O'; break;
        case 0x99:case 0x9A:case 0x9B:case 0x9C: msgPropre+='U'; break;
        default: break;
      }
      i+=2; continue;
    }
    if (c >= 0x80) { i++; continue; }
    msgPropre += (char)c;
    i++;
  }
  if ((int)msgPropre.length() > 155) msgPropre = msgPropre.substring(0, 155);
  Serial.println("[SMS] Msg propre (" + String(msgPropre.length()) + " oct.) : " + msgPropre.substring(0,60));

  // ── Envoi avec retry (2 tentatives) ─────────────────────────────────────
  for (int tentative = 0; tentative < 2; tentative++) {
    if (tentative > 0) {
      Serial.println("[SMS] Retry " + String(tentative) + "/2...");
      delay(5000);
      while (simSerial.available()) simSerial.read();
      envoyerAT("AT+CMGF=1", 2000);
      delay(500);
    }

    while (simSerial.available()) simSerial.read();
    simSerial.println("AT+CMGS=\"" + numTel + "\"");
    delay(1200);

    // Attendre prompt >
    unsigned long tPr = millis();
    bool promptOk = false;
    String repPr = "";
    while (millis() - tPr < 8000) {
      while (simSerial.available()) {
        char c = simSerial.read();
        repPr += c;
        if (c == '>') { promptOk = true; break; }
      }
      if (promptOk) break;
    }
    if (!promptOk) {
      Serial.println("[SMS] Pas de prompt > : " + repPr.substring(0,30));
      continue;
    }

    Serial.println("[SMS] Prompt > recu - envoi...");
    simSerial.print(msgPropre);
    delay(300);
    simSerial.write(26);  // Ctrl+Z

    // Attendre confirmation reseau (15s max)
    String repCmgs = "";
    unsigned long tCmgs = millis();
    while (millis() - tCmgs < 15000) {
      while (simSerial.available()) repCmgs += (char)simSerial.read();
      if (repCmgs.indexOf("+CMGS")      != -1) break;
      if (repCmgs.indexOf("+CMS ERROR") != -1) break;
      if (repCmgs.indexOf("ERROR")      != -1) break;
    }
    Serial.println("[SMS] Reponse : " + repCmgs.substring(0,50));

    if (repCmgs.indexOf("+CMGS") != -1) {
      Serial.println("[SMS] SMS confirme par le reseau !");
      marquerSmsEnvoye();
      return;  // succes
    }
    Serial.println("[SMS] Tentative " + String(tentative+1) + " echouee");
  }
  Serial.println("[SMS] SMS non envoye apres 2 tentatives");
}




void marquerSmsEnvoye() {
  // POST → Firebase sms_a_envoyer/envoye.json avec override PUT
  // (Firebase direct — pas de Render, pas de cold start)
  envoyerAT("AT+HTTPTERM", 1000); delay(500);
  if (envoyerAT("AT+HTTPINIT", 5000).indexOf("OK") == -1) {
    Serial.println("[SMS] marquerSmsEnvoye : HTTPINIT echoue");
    return;
  }

  String url = "https://" + String(FIREBASE_HOST)
             + "/stations/" + STATION_ID + "/sms_a_envoyer/envoye.json"
             + "?auth=" + String(FIREBASE_AUTH);

  envoyerAT("AT+HTTPPARA=\"URL\",\"" + url + "\"", 3000);
  envoyerAT("AT+HTTPPARA=\"CONTENT\",\"application/json\"", 3000);
  envoyerAT("AT+HTTPPARA=\"USERDATA\",\"X-HTTP-Method-Override: PUT\"", 2000);

  String jsonTrue = "true";
  simSerial.println("AT+HTTPDATA=" + String(jsonTrue.length()) + ",5000");
  if (attendreReponse("DOWNLOAD", 5000)) {
    simSerial.print(jsonTrue); delay(2000);
    simSerial.println("AT+HTTPACTION=1");
    String repMark = ""; unsigned long t = millis();
    while (millis() - t < 10000) {
      while (simSerial.available()) repMark += (char)simSerial.read();
      if (repMark.indexOf("+HTTPACTION") != -1) break;
    }
    bool ok = repMark.indexOf(",200,") != -1;
    Serial.println("[SMS] Marque envoye : " + String(ok ? "OK \u2705" : "ECHEC") + " " + repMark.substring(0,30));
  }
  envoyerAT("AT+HTTPTERM");
}

// ============================================================
// LOOP
// ============================================================
void loop() {
  // ── MODE TEST : envoi toutes les 30 secondes ──
  // Remplacer INTERVALLE_TEST par 0 pour revenir aux créneaux 3x/jour
  static unsigned long dernierEnvoiTest = 0;
  #define INTERVALLE_TEST 30000
  if (millis() - dernierEnvoiTest < INTERVALLE_TEST) return;
  dernierEnvoiTest = millis();
  {

    // ── Lecture capteurs (avec filtrage) ──────────────────────
    float temperature = lireTemperature();
    float humiditeAir = lireHumiditeAir();
    float humiditeSol = lireHumiditeSol();
    float vitesseVent = lireVitesseVent();

    // ── GPS ────────────────────────────────────────────────────
    if (sim4GReady) lireGPS();

    // ── Affichage ──────────────────────────────────────────────
   Serial.println("\n================================");
    Serial.println("   RELEVÉ CAPTEURS");
    Serial.println("================================");
    Serial.printf("  Température  : %.1f °C", temperature);
    if (temperature > 35) Serial.print("  ⚠️  CHAUD");
    Serial.println();
    Serial.printf("  Humidité air : %.1f %%", humiditeAir);
    if (humiditeAir > 80) Serial.print("  ⚠️  HUMIDE");
    Serial.println();
    Serial.printf("  Humidité sol : %.1f %%", humiditeSol);
    if (humiditeSol < 25) Serial.print("  ⚠️  SEC");
    Serial.println();
    Serial.printf("  Vitesse vent : %.2f km/h", vitesseVent);
    if (vitesseVent > 45) Serial.print("  ⚠️  FORT");
    Serial.println();
    Serial.println("--------------------------------");
    Serial.printf("  GPS          : %s\n",
                  gpsFixOk ? "✓ FIX OK" : "⏳ Pas encore de fix");
    if (gpsFixOk)
      Serial.printf("  Position     : %.6f, %.6f (%.1fm)\n",
                    gpsLatitude, gpsLongitude, gpsAltitude);
    Serial.println("--------------------------------");
    Serial.printf("  Mode réseau  : %s\n",
                  modeActif == MODE_WIFI ? "WiFi" :
                  modeActif == MODE_4G   ? "4G SIM7600E" : "AUCUN");
    Serial.println("================================\n");
    
       // Ne pas envoyer le premier cycle — vent non initialisé
    if (!premierCycleIgnore) {
      premierCycleIgnore = true;
      Serial.println("[TIMING] Premier cycle ignoré — vent en cours d'initialisation");
      return;
    }
    // ── Décision de connexion ──────────────────────────────────
    // Re-tente WiFi à chaque cycle (si réseau est revenu)
    bool wifiDispo = connecterWiFi();

    if (wifiDispo) {
      // WiFi prioritaire
      if (modeActif != MODE_WIFI) {
        Serial.println("[MODE] Basculement → WiFi");
        modeActif = MODE_WIFI;
        // Re-sync NTP si on revient sur WiFi
        configTime(0, 0, "pool.ntp.org", "time.nist.gov");
      }
      envoyerFirebaseWiFi(temperature, humiditeAir, vitesseVent, humiditeSol);

    } else if (sim4GReady) {
      // Fallback 4G
      if (modeActif != MODE_4G) {
        Serial.println("[MODE] Basculement → 4G (WiFi absent)");
        modeActif = MODE_4G;
      }
      bool ok = envoyerFirebase4G(temperature, humiditeAir, vitesseVent, humiditeSol);
      if (!ok) {
        Serial.println("[4G] Echec envoi — réinit SIM7600E...");
        sim4GReady = initSIM7600();
      }

    } else {
      Serial.println("[WARN] Aucune connexion — données non envoyées");
      modeActif = MODE_AUCUN;
    }
  }
  // Vérifier si un SMS est à envoyer depuis Firebase
    if (sim4GReady) {
      String msgSMS = "", telSMS = "";
      if (lireSmsAEnvoyer(msgSMS, telSMS)) {
        envoyerSMS(telSMS, msgSMS);
      }
    }
}
