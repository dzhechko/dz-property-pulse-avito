document.addEventListener('DOMContentLoaded', function() {
    // Handle scraping form submission
    const scrapingForm = document.getElementById('scraping-form');
    const scrapingStatus = document.getElementById('scraping-status');
    const scrapeButton = document.getElementById('scrape-button');
    
    if (scrapingForm) {
        scrapingForm.addEventListener('submit', function(event) {
            // Show scraping status and disable button
            if (scrapingStatus) {
                scrapingStatus.classList.remove('d-none');
            }
            if (scrapeButton) {
                scrapeButton.disabled = true;
                scrapeButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Scraping...';
            }
        });
    }
    
    // Handle analysis form submission
    const analysisForm = document.getElementById('analysis-form');
    const analysisStatus = document.getElementById('analysis-status');
    const analyzeButton = document.getElementById('analyze-button');
    
    if (analysisForm) {
        analysisForm.addEventListener('submit', function(event) {
            // Show analysis status and disable button
            if (analysisStatus) {
                analysisStatus.classList.remove('d-none');
            }
            if (analyzeButton) {
                analyzeButton.disabled = true;
                analyzeButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Analyzing...';
            }
        });
    }
    
    // Handle parameter selection change - update description and default bins
    const parameterSelect = document.getElementById('parameter');
    const parameterDescription = document.querySelector('.parameter-description');
    const binsInput = document.getElementById('bins');
    
    if (parameterSelect && parameterDescription && binsInput) {
        parameterSelect.addEventListener('change', function(event) {
            const selectedOption = this.options[this.selectedIndex];
            const defaultBins = selectedOption.dataset.bins || 30;
            
            // Update bins value
            binsInput.value = defaultBins;
            
            // Update description based on selection
            const descriptions = {
                'price': 'Analyze distribution of property prices with statistical metrics',
                'area': 'Analyze distribution of property sizes in square meters',
                'rooms': 'Analyze distribution of room counts in properties',
                'seller_rating': 'Analyze distribution of seller ratings',
                'views': 'Analyze distribution of listing view counts'
            };
            
            parameterDescription.textContent = descriptions[this.value] || 'Analyze distribution of the selected parameter';
        });
    }
    
    // Handle reset bins button
    const resetBinsButton = document.getElementById('reset-bins');
    
    if (resetBinsButton && parameterSelect && binsInput) {
        resetBinsButton.addEventListener('click', function(event) {
            const selectedOption = parameterSelect.options[parameterSelect.selectedIndex];
            const defaultBins = selectedOption.dataset.bins || 30;
            binsInput.value = defaultBins;
        });
    }
    
    // Handle example URL links
    const exampleUrls = document.querySelectorAll('.example-url');
    const urlInput = document.getElementById('url');
    
    if (exampleUrls.length > 0 && urlInput) {
        exampleUrls.forEach(link => {
            link.addEventListener('click', function(event) {
                event.preventDefault();
                urlInput.value = this.dataset.url;
                // Scroll to the form
                urlInput.scrollIntoView({ behavior: 'smooth' });
                urlInput.focus();
            });
        });
    }
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    if (tooltipTriggerList.length > 0) {
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
    
    // Handle password visibility toggle
    const togglePasswordButtons = document.querySelectorAll('.toggle-password');
    if (togglePasswordButtons.length > 0) {
        togglePasswordButtons.forEach(button => {
            button.addEventListener('click', function() {
                const targetId = this.getAttribute('data-target');
                const inputField = document.getElementById(targetId);
                
                if (inputField) {
                    // Toggle password visibility
                    if (inputField.type === 'password') {
                        inputField.type = 'text';
                        this.innerHTML = '<i class="fas fa-eye-slash"></i>';
                    } else {
                        inputField.type = 'password';
                        this.innerHTML = '<i class="fas fa-eye"></i>';
                    }
                }
            });
        });
    }
});
