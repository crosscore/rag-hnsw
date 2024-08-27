/* frontend/static/script.js */

document.addEventListener("DOMContentLoaded", function() {
    var searchInput = document.getElementById("search-input");
    var searchButton = document.getElementById("search-button");
    var searchResults = document.getElementById("search-results");
    var categorySelect = document.getElementById("category-select");
    var firstAiResponse = document.getElementById("first-ai-response");
    var finalAiResponse = document.getElementById("final-ai-response");

    var socket = new WebSocket("ws://" + window.location.host + "/ws");

    socket.onopen = function() {
        console.log("WebSocket connection established");
    };

    socket.onmessage = function(event) {
        try {
            var data = JSON.parse(event.data);
            console.log("Received data:", data);
            if (data.error) {
                searchResults.innerHTML += "<p>Error: " + data.error + "</p>";
            } else if (data.manual_results) {
                console.log("Displaying manual results:", data.manual_results);
                displayResults(data.manual_results, "Manual Search Results", 4);
            } else if (data.faq_results) {
                console.log("Displaying FAQ results:", data.faq_results);
                displayResults(data.faq_results, "FAQ Search Results", 3);
            } else if (data.first_ai_response_chunk) {
                var responseP = firstAiResponse.querySelector("p") || firstAiResponse.appendChild(document.createElement("p"));
                responseP.innerHTML += data.first_ai_response_chunk;
            } else if (data.first_ai_response_end) {
                var responseP = firstAiResponse.querySelector("p");
                if (responseP) {
                    responseP.innerHTML += "<br><em>(First response complete)</em>";
                }
            } else if (data.pdf_info) {
                displayPdfInfo(data.pdf_info);
            } else if (data.ai_response_chunk) {
                var responseP = finalAiResponse.querySelector("p") || finalAiResponse.appendChild(document.createElement("p"));
                responseP.innerHTML += data.ai_response_chunk;
            } else if (data.ai_response_end) {
                var responseP = finalAiResponse.querySelector("p");
                if (responseP) {
                    responseP.innerHTML += "<br><em>(Final response complete)</em>";
                }
            }
        } catch (error) {
            console.error("Error parsing WebSocket message:", error);
        }
    };

    socket.onerror = function() {
        searchResults.innerHTML = "<p>Error: Connection failed. Please try again later.</p>";
    };

    searchButton.addEventListener("click", function() {
        var query = searchInput.value;
        var category = categorySelect.value;
        if (query && category) {
            console.log("Sending search request:", { question: query, category: parseInt(category) });
            socket.send(JSON.stringify({ question: query, category: parseInt(category) }));
            searchResults.innerHTML = "<p>Searching...</p>";
            firstAiResponse.innerHTML = "<h2>First AI Response:</h2>";
            finalAiResponse.innerHTML = "<h2>Final AI Response:</h2>";
        } else {
            searchResults.innerHTML = "<p>Please enter a query and select a category</p>";
        }
    });

    function displayPdfInfo(pdfInfo) {
        var pdfInfoHTML = "";
        pdfInfoHTML += pdfInfo.map((pdf, index) => {
            var link = `pdf/manual/${encodeURIComponent(pdf.category)}/${encodeURIComponent(pdf.file_name)}?start_page=${pdf.start_page}&end_page=${pdf.end_page}`;
            return `
                <div class="pdf-info">
                    <h3>${index + 1}. <a href="${link}" target="_blank">/manual/${pdf.category}/${pdf.file_name}, p.${pdf.start_page}-p.${pdf.end_page}</a></h3>
                </div>
            `;
        }).join('');
        firstAiResponse.innerHTML += pdfInfoHTML;
    }

    function displayResults(results, title, maxResults) {
        var resultsHTML = "<h2>" + title + "</h2>";
        if (results && results.length > 0) {
            resultsHTML += generateResultsHTML(results.slice(0, maxResults), title.toLowerCase().includes("manual") ? "manual" : "faq");
        } else {
            resultsHTML += "<p>No results found.</p>";
        }
        searchResults.innerHTML += resultsHTML;
    }

    function generateResultsHTML(results, type) {
        return results.map((result, index) => {
            var link = `pdf/${type}/${result.category}/${encodeURIComponent(result.file_name)}?page=${result.page}`;
            var linkText = `/${type}/${result.category}/${result.file_name}, p.${result.page}`;

            return `
                <div class="result">
                    <h3>${index + 1}. <a href="${link}" target="_blank">${linkText}</a></h3>
                    <!-- <p>Category: ${result.category}</p> -->
                    ${type === 'faq' ? `<p>FAQ No: ${result.faq_no}</p>` : ''}
                    <p>${result.chunk_text || "No text available"}</p>
                    <p>Distance: ${result.distance.toFixed(4)}</p>
                </div>
            `;
        }).join('');
    }
});
