document.getElementById("menu-icon").addEventListener("click", function () {
    document.getElementById("nav-list").classList.toggle("active");
});

// Lepší verze - ošetří i pomalejší načtení iframe
var iframes = [document.getElementById('tabulkaIframe'), document.getElementById('zapasyIframe')];

iframes.forEach(function (iframe) {
    iframe.addEventListener('load', function () {
        var iframeDoc = iframe.contentDocument || iframe.contentWindow.document;

        if (iframeDoc && iframeDoc.readyState === "complete") {
            applyStylesAndHighlight(iframeDoc);
        } else {
            // Kdyby ještě nebylo načteno, čekáme malinko
            setTimeout(function () {
                applyStylesAndHighlight(iframeDoc);
            }, 100);
        }
    });
});

// Funkce pro přidání stylu a zvýraznění "Ponikla"
function applyStylesAndHighlight(doc) {
    if (!doc) return;

    // Přidání CSS stylu
    var style = doc.createElement('style');
    style.innerHTML = `
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        table th, table td {
            padding: 10px;
            text-align: left;
            border: 1px solid #0056b3;
            background-color: #f8f9fa;
        }
        table th {
            background-color: #0056b3;
            color: white;
            font-weight: bold;
        }
        table tr:nth-child(even) {
            background-color: #e9ecef;
        }
        table tr:hover {
            background-color: #dfe3e9;
        }
        table td {
            color: #333;
        }

        @media (max-width: 768px) {
            table {
                font-size: 12px;
            }
            table th, table td {
                padding: 8px;
            }
        }

        .highlight {
            background-color: #cce5ff !important;
            font-weight: bold;
        }
    `;
    doc.head.appendChild(style);

    // Zvýraznění řádků obsahujících "Ponikla"
    var rows = doc.querySelectorAll('tr');
    rows.forEach(function (row) {
        if (row.innerText.includes('TJ Poniklá')) {
            row.classList.add('highlight');
        }
    });
}
