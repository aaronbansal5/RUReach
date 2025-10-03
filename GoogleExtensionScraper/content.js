const MAX_PAGES = 50;
const SCRAPE_DELAY_MS = 2000;

function extractNames() {

    let scrapedNames = new Set(JSON.parse(localStorage.getItem('scrapedNames') || '[]')); 

    const urlParams = new URLSearchParams(window.location.search);
    let currentPage = parseInt(urlParams.get('page')) || 0;

    if (currentPage >= MAX_PAGES) {
        
        const nameList = Array.from(scrapedNames);
        const count = nameList.length;
        const csvContent = "data:text/csv;charset=utf-8," + "Name\n" + nameList.join('\n');
        
        // Final Data Output
        console.log(`\n\n--- FINAL SCRAPE COMPLETE (${count} Total Names) ---\n`);
        console.log(nameList.join('\n'));
        console.log('\n----------------------------------------\n\n');

        // Create a temporary link to download the CSV file
        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", `Rutgers_Professor_Names_${count}.csv`);
        
        // Simulate a click to download the file
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        localStorage.removeItem('scrapedNames');
        
        alert(`✅ ALL PAGES COMPLETE! Extracted ${count} professor names and **downloaded the data as a CSV file**.`);

        return;
    }
    
    const nameElements = document.querySelectorAll('h3.title span');
    
    // Process the list of elements to get the text content
    const names = Array.from(nameElements)
        .map(el => el.textContent.trim())
        // Filter out empty strings and ensure uniqueness
        .filter(name => name.length > 3)
        .filter((value, index, self) => self.indexOf(value) === index); 

    if (names.length > 0) {
        const nameList = names.join('\n');
        const count = names.length;

        // Log the results in the browser's console (press F12 to see)
        console.log(`\n\n--- EXTRACTED PROFESSOR NAMES (${count}) ---\n`);
        console.log(nameList);
        console.log('\n----------------------------------------\n\n');

        // Save to localStorage
        names.forEach(name => scrapedNames.add(name));
        localStorage.setItem('scrapedNames', JSON.stringify(Array.from(scrapedNames)));

    } else {
        alert('❌ ERROR: Could not find any professor names. The selector may need adjustment.');
    }

    setTimeout(() => {
        const nextUrl = `https://www.researchwithrutgers.com/en/persons/?page=${currentPage + 1}`;
        console.log(`Navigating to Page ${currentPage + 1}...`);
        window.location.href = nextUrl;
    }, SCRAPE_DELAY_MS);
}

// Run the function after a short delay (1.5 seconds) to ensure all content is loaded.
window.addEventListener('load', () => {
    setTimeout(extractNames, 1500); 
});