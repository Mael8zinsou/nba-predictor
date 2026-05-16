/*******************************LISTENER*******************************/

document.getElementById("btn_getparams").addEventListener("click", getParams); //19 params
document.getElementById("btn_getdecisionbyname").addEventListener("click", getDecisionById);
document.getElementById("btn_getficclassification").addEventListener("click", getFilClassification);

/***************VAR GET DECISION & GET DECISION OF A NAME *************/

function getDecisionById() {

  NameOfPlayer = document.getElementById("NameOfPlayer").value;

  var Decisions_by_name = {
    // "url": "http://localhost:8080/api/nba/info?Name=" + NameOfPlayer,
    "url": "/api/nba/info?Name=" + NameOfPlayer,
    "method": "GET",
    "timeout": 0
  };

  // on execute notre requête HTTP et on attend notre réponse à l'aide d'une promesse (une fonction qui attend une valeur).
  $.ajax(Decisions_by_name).done(function (response) {
    //console.log(response);

    txt = document.getElementById("txt");

    // CAS 1 : Le joueur n'existe pas (champ error dans data)
    if (response && response.error) {
      txt.style.color = "red";
      txt.innerHTML = response.error;
      return;  // On arrête ici
    }

    // CAS 2 : Le joueur existe et renvoie une décision
    if (response && response.decision) {

      let x = response.decision[0];  
      // JSON.parse(myJSON); : from json data to js Object (ancienne version)
      // x = myObj.decision["0"];  récupère la valeur prédite (ancienne version)

      if (x == 1.0 || x === 1.0) {
        txt.style.color = "green";
        txt.innerHTML = "Vous pouvez recruter!";
      } else {
        txt.style.color = "red";
        txt.innerHTML = "Vous ne devez pas recruter!";
      }

      return;
    }

    // CAS INATTENDU : le JSON ne contient ni erreur ni décision
    txt.style.color = "red";
    txt.innerHTML = "Réponse inconnue du serveur.";
  });
}



/***************VARs GET Params & GET DECISION OF Params*******************/

function getParams() {

  TOV = document.getElementById("TOV").value;
  GP = document.getElementById("GP").value;
  MIN = document.getElementById("MIN").value;
  PTS = document.getElementById("PTS").value;
  FGM = document.getElementById("FGM").value;
  FGA = document.getElementById("FGA").value;
  FGP = document.getElementById("FGP").value;
  PM = document.getElementById("PM").value;
  PA = document.getElementById("PA").value;
  PAP = document.getElementById("PAP").value;
  FTM = document.getElementById("FTM").value;
  FTA = document.getElementById("FTA").value;
  FTP = document.getElementById("FTP").value;
  OREB = document.getElementById("OREB").value;
  DREB = document.getElementById("DREB").value;
  REB = document.getElementById("REB").value;
  AST = document.getElementById("AST").value;
  STL = document.getElementById("STL").value;
  BLK = document.getElementById("BLK").value;

  var Player_params = {
    "url":
      // "http://localhost:8080/api/nba/predict?"
      "/api/nba/predict?"
      + "TOV=" + TOV + "&GP=" + GP + "&MIN=" + MIN + "&PTS=" + PTS
      + "&FGM=" + FGM + "&FGA=" + FGA + "&FGP=" + FGP + "&PM=" + PM
      + "&PA=" + PA + "&PAP=" + PAP + "&FTM=" + FTM + "&FTA=" + FTA
      + "&FTP=" + FTP + "&OREB=" + OREB + "&DREB=" + DREB + "&REB=" + REB
      + "&AST=" + AST + "&STL=" + STL + "&BLK=" + BLK,

    "method": "GET",
    "timeout": 0
  };

  // on execute notre requête HTTP et on attend la réponse
  $.ajax(Player_params).done(function (response) {

    txt = document.getElementById("txt");

    // CAS décision successful
    let x = response.prediction.decision[0];

    if (x == 1.0 || x === 1.0) {
      txt.style.color = "green";
      txt.innerHTML = "Vous pouvez recruter ce joueur!";
    } else {
      txt.style.color = "red";
      txt.innerHTML = "Vous ne devez pas recruter ce joueur!";
    }
    return;
  });
}


/************************FILE DATASET***********************/

// 1) Quand on clique sur le bouton, on ouvre la fenêtre de sélection
document.getElementById("btn_getficclassification").addEventListener("click", function () {
    document.getElementById("datasetFile").click();
});

// 2) Quand l'utilisateur a choisi un fichier, on l'envoie automatiquement à l'API
document.getElementById("datasetFile").addEventListener("change", function () {
    getFilClassification();
});

function getFilClassification() {

  let fileInput = document.getElementById("datasetFile");
  let file = fileInput.files[0];

  if (!file) {
    alert("Veuillez sélectionner un fichier CSV.");
    return;
  }

  let formData = new FormData();
  formData.append("file", file);

  $.ajax({
    // url: "http://localhost:8080/api/nba/dataset",
    url: "/api/nba/dataset",
    method: "POST",
    data: formData,
    contentType: false,
    processData: false
  })
  .done(function(response) {

    txt = document.getElementById("txt");

    // CAS erreur renvoyée par l'API
    if (response.error) {
      txt.style.color = "red";
      txt.innerHTML = response.error;
      return;
    }

    // Récupération des valeurs retournées
    const total = response.total_players;
    const count = response.recruitable_count;
    const positions = response.recruitable_positions;

    // Si aucun joueur n’est recrutable
    if (count === 0) {
      txt.style.color = "red";
      txt.innerHTML = `Aucun joueur recrutable sur ${total}.`;
      return;
    }
    
    // Si certains joueurs sont recrutable
    txt.style.color = "blue";
    txt.innerHTML = `
        Le dataset contient <b>${total}</b> joueurs.<br>
        <b>${count}</b> sont recrutables.<br>
        Indices : <b>[${positions.join(", ")}]</b>`;

    // CAS décision reçue (ancienne version)
    /**if (response.decision) {
      let x = response.decision[0];

      if (x === 1 || x === 1.0) {
        txt.style.color = "green";
        txt.innerHTML = "Le dataset est valide : vous pouvez recruter !";
      } else {
        txt.style.color = "red";
        txt.innerHTML = "Le dataset est valide : vous ne devez pas recruter.";
      }
      return;
    }**/

    // CAS inconnu (ancienne version)
    //txt.style.color = "red";
    //txt.innerHTML = "Réponse du serveur : " + JSON.stringify(response);
  })
  .fail(function () {
    txt = document.getElementById("txt");
    txt.style.color = "red";
    txt.innerHTML = "Impossible de contacter le serveur.";
  });
}