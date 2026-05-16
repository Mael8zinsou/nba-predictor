// ***********************SIGNATURE POUR FOOTER*******************************
setInterval(() => {
    let sig = document.getElementById("signature");
    if (!sig || sig.innerText.trim() !== "Réalisé par Ketsia MULAPI - Juin@2021") {
        if (!sig) {
            sig = document.createElement("footer");
            sig.id = "signature";
            document.body.appendChild(sig);
        }
        sig.innerText = "Réalisé par Ketsia MULAPI - Juin@2021";
        sig.style.userSelect = "none";
        sig.style.pointerEvents = "none";
    }
}, 500);