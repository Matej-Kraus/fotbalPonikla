document.getElementById("menu-icon").addEventListener("click", function () {
    document.getElementById("nav-list").classList.toggle("active");
});



window.addEventListener('load', function () {
    // Seznam iframe prvků
    var iframes = [document.getElementById('tabulkaIframe'), document.getElementById('zapasyIframe')];

    iframes.forEach(function (iframe) {
        var iframeDoc = iframe.contentDocument || iframe.contentWindow.document;

        // Pokud iframe obsahuje stránku
        if (iframeDoc) {
            var style = iframeDoc.createElement('style');
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
                    iframe {
                        width: 100%;
                    }
                }
            `;
            iframeDoc.head.appendChild(style);
        }
    });
});

