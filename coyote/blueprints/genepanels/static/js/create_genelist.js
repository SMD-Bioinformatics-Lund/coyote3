document.addEventListener('DOMContentLoaded', function() {
    const nameField = document.getElementById('nameField');
    const displaynameField = document.getElementById('displaynameField');
    const nameError = document.getElementById('nameError');
    const displaynameError = document.getElementById('displaynameError');
    const assayContainer = document.getElementById('assay-container');
    const newAssayInput = document.getElementById('new_assay_input');
    const assaysField = document.getElementById('assays_field');

    function updateAssaysField() {
        const assayElements = assayContainer.querySelectorAll('.assay-item span');
        const assays = Array.from(assayElements).map(span => span.textContent);
        assaysField.value = assays.join(',');
    }

    function createAssayElement(assayName) {
        const assayDiv = document.createElement('div');
        assayDiv.className = 'assay-item flex items-center space-x-2 bg-blue-200 rounded-lg px-3 py-2';
        assayDiv.innerHTML = `<span>${assayName}</span><button type="button" class="text-red-500 hover:text-red-700 remove-assay">x</button>`;
        
        assayDiv.querySelector('.remove-assay').addEventListener('click', function() {
            assayDiv.remove();
            updateAssaysField();
        });

        return assayDiv;
    }

    // Handle adding new assays via Enter key
    newAssayInput.addEventListener('keydown', function(event) {
        if (event.key === 'Enter' && this.value.trim() !== '') {
            event.preventDefault();
            const newAssay = this.value.trim();
            const assays = newAssay.split(',').map(a => a.trim()).filter(a => a !== '');
            assays.forEach(assay => {
                const assayElement = createAssayElement(assay);
                assayContainer.appendChild(assayElement);
            });
            this.value = '';
            updateAssaysField();
        }
    });

    // Handle adding existing suggested assays
    document.querySelectorAll('.suggestion-item .add-assay').forEach(button => {
        button.addEventListener('click', function() {
            const assayName = this.previousElementSibling.textContent;
            const assayElement = createAssayElement(assayName);
            assayContainer.appendChild(assayElement);
            this.closest('.suggestion-item').remove();
            updateAssaysField();
        });
    });

    // Name and display name validation
    function validateField(field, errorSpan, validationUrl) {
        field.addEventListener('blur', function() {
            const value = field.value.trim();
            if (value !== '') {
                fetch(validationUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ value: value })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.exists) {
                        errorSpan.textContent = `${field.name} already exists. Please choose a different ${field.name}.`;
                    } else {
                        errorSpan.textContent = '';
                    }
                })
                .catch(error => console.error('Error:', error));
            }
        });
    }

    validateField(nameField, nameError, validateNameUrl);
    validateField(displaynameField, displaynameError, validateDisplayNameUrl);
});
