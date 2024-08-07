/* rag-hnsw/frontend/static/script.js */

document.addEventListener("DOMContentLoaded", () => {
	const searchInput = document.getElementById("search-input");
	const searchButton = document.getElementById("search-button");
	const searchResults = document.getElementById("search-results");
	const categorySelect = document.getElementById("category-select");
	const aiResponse = document.getElementById("ai-response");

	let socket = new WebSocket("ws://" + window.location.host + "/ws");

	socket.onopen = () => console.log("WebSocket connection established");

	socket.onmessage = (event) => {
		try {
			const data = JSON.parse(event.data);
			if (data.error) {
				searchResults.innerHTML = `<p>Error: ${data.error}</p>`;
			} else if (data.results && data.chunk_texts) {
				displayResults(data.results);
				aiResponse.innerHTML = "<h2>AI Response:</h2><p></p>";
			} else if (data.ai_response_chunk) {
				const responseP = aiResponse.querySelector("p");
				responseP.innerHTML += data.ai_response_chunk;
			} else if (data.ai_response_end) {
				const responseP = aiResponse.querySelector("p");
				responseP.innerHTML += "<br><em>(Response complete)</em>";
			}
		} catch (error) {
			console.error("Error parsing WebSocket message:", error);
		}
	};

	socket.onerror = () => {
		searchResults.innerHTML =
			"<p>Error: Connection failed. Please try again later.</p>";
	};

	searchButton.addEventListener("click", () => {
		const query = searchInput.value;
		const category = categorySelect.value;
		if (query && category) {
			socket.send(
				JSON.stringify({ question: query, category: category })
			);
			searchResults.innerHTML = "<p>Searching...</p>";
			aiResponse.innerHTML =
				"<h2>AI Response:</h2><p>Waiting for results...</p>";
		} else {
			searchResults.innerHTML =
				"<p>Please enter a query and select a category</p>";
		}
	});

	function displayResults(results) {
		if (results.length === 0) {
			searchResults.innerHTML =
				"<p>No results found. AI will attempt to answer based on general knowledge.</p>";
			return;
		}

		let resultsHTML = "<h2>Search Results</h2>";
		results.forEach((result, index) => {
			resultsHTML += `
                <div class="result">
                    <h3>${index + 1}. <a href="${
				result.link
			}" target="_blank">${result.link_text}</a></h3>
                    <p>Category: ${result.category}</p>
                    <p>${result.chunk_text}</p>
                    <p>Distance: ${result.distance.toFixed(4)}</p>
                </div>
            `;
		});
		searchResults.innerHTML = resultsHTML;
	}
});
