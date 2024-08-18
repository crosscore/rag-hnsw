/* rag-hnsw/frontend/static/script.js */

document.addEventListener("DOMContentLoaded", function() {
    var searchInput = document.getElementById("search-input");
    var searchButton = document.getElementById("search-button");
    var searchResults = document.getElementById("search-results");
    var categorySelect = document.getElementById("category-select");
    var aiResponse = document.getElementById("ai-response");

    var socket = new WebSocket("ws://" + window.location.host + "/ws");

    socket.onopen = function() {
        console.log("WebSocket connection established");
    };

    socket.onmessage = function(event) {
        try {
            var data = JSON.parse(event.data);
            if (data.error) {
                searchResults.innerHTML = "<p>Error: " + data.error + "</p>";
            } else if (data.manual_results) {
                displayResults(data.manual_results, "Manual Search Results");
            } else if (data.faq_results) {
                displayResults(data.faq_results, "FAQ Search Results");
            } else if (data.ai_response_chunk) {
                var responseP = aiResponse.querySelector("p") || aiResponse.appendChild(document.createElement("p"));
                responseP.innerHTML += data.ai_response_chunk;
            } else if (data.ai_response_end) {
                var responseP = aiResponse.querySelector("p");
                if (responseP) {
                    responseP.innerHTML += "<br><em>(Response complete)</em>";
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
            socket.send(JSON.stringify({ question: query, category: category }));
            searchResults.innerHTML = "<p>Searching...</p>";
            aiResponse.innerHTML = "<h2>AI Response:</h2>";
        } else {
            searchResults.innerHTML = "<p>Please enter a query and select a category</p>";
        }
    });

    function displayResults(results, title) {
        var resultsHTML = "<h2>" + title + "</h2>";
        results.forEach(function(result, index) {
            var documentType = result.document_type;
            var category = result.category;
            var fileName = result.file_name;
            var page = result.page;
            var link = "pdf/" + documentType + "/" + category + "/" + encodeURIComponent(fileName) + "?page=" + page;
            var linkText = "/" + documentType + "/" + category + "/" + fileName + ", p." + page;

            resultsHTML +=
                '<div class="result">' +
                    "<h3>" + (index + 1) + '. <a href="' + link + '" target="_blank">' + linkText + "</a></h3>" +
                    "<p>Category: " + result.category + "</p>" +
                    "<p>" + result.page_text + "</p>" +
                    "<p>Distance: " + result.distance.toFixed(4) + "</p>" +
                "</div>";
        });
        searchResults.innerHTML += resultsHTML;
    }
});
