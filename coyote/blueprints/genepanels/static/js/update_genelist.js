document.addEventListener('DOMContentLoaded', function() {
  // Elements
  const genesInputContainer = document.getElementById('genes-input-container');
  const genesInput = document.getElementById('genes-input');
  const genesField = document.getElementById('genes_field');

  const assaysInputContainer = document.getElementById('assays-input-container');
  const assaysInput = document.getElementById('assays-input');
  const assaysField = document.getElementById('assays_field');
  const assaySuggestions = document.getElementById('assay-suggestions');

  const nameField = document.getElementById('nameField');
  const nameError = document.getElementById('nameError');
  const displaynameField = document.getElementById('displaynameField');
  const displaynameError = document.getElementById('displaynameError');

  const versionField = document.getElementById('versionField');
  const versionError = document.getElementById('versionError');

  let versionValid = true;
  let nameValid = true;
  let displaynameValid = true;

  // Function to update the hidden fields
  function updateHiddenField(container, field) {
      const values = [];
      container.querySelectorAll('.item-tag').forEach(tag => {
          values.push(tag.dataset.value);
      });
      field.value = values.join(',');
  }

  // Function to create a tag element
  function createTagElement(name, container, field) {
      const tagDiv = document.createElement('div');
      tagDiv.className = 'item-tag flex items-center space-x-2 bg-blue-200 rounded-lg px-3 py-1 my-1 mr-2';
      tagDiv.dataset.value = name;
      tagDiv.innerHTML = `<span>${name}</span><button type="button" class="text-red-500 hover:text-red-700 remove-item">x</button>`;

      tagDiv.querySelector('.remove-item').addEventListener('click', function() {
          tagDiv.remove();
          updateHiddenField(container, field);
          updateAssaySuggestions();  // Update suggestions when an assay is removed
      });

      container.insertBefore(tagDiv, container.querySelector('input'));
      updateHiddenField(container, field);
  }

  // Function to process the input and create tags
  function processInput(input, container, field) {
      const values = input.value.trim().split(/\s+/);
      values.forEach(value => {
          if (value) {
              createTagElement(value, container, field);
          }
      });
      input.value = '';
  }

  // Function to update assay suggestions
  function updateAssaySuggestions() {
      const currentAssays = assaysField.value.split(',').map(assay => assay.trim());
      const availableAssays = JSON.parse(availableAssaysJson);
      assaySuggestions.innerHTML = '';

      availableAssays.forEach(assay => {
          if (!currentAssays.includes(assay)) {
              const suggestionButton = document.createElement('button');
              suggestionButton.className = 'suggestion-item bg-green-200 hover:bg-green-300 text-green-800 font-bold py-1 px-2 rounded-lg flex items-center';
              suggestionButton.innerHTML = `<span class="mr-2">${assay}</span><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3-7a1 1 0 01-1 1H8a1 1 0 010-2h4a1 1 0 011 1z" clip-rule="evenodd" /></svg>`;
              suggestionButton.addEventListener('click', function() {
                  createTagElement(assay, assaysInputContainer, assaysField);
                  updateAssaySuggestions();
              });
              assaySuggestions.appendChild(suggestionButton);
          }
      });

      assaySuggestions.style.display = assaySuggestions.innerHTML.trim() ? 'flex' : 'none';
  }

  // Setup initial tags for genes and assays
  const existingGenes = genesField.value.split(',');
  existingGenes.forEach(gene => {
      if (gene.trim()) {
          createTagElement(gene.trim(), genesInputContainer, genesField);
      }
  });

  const existingAssays = assaysField.value.split(',');
  existingAssays.forEach(assay => {
      if (assay.trim()) {
          createTagElement(assay.trim(), assaysInputContainer, assaysField);
      }
  });

  updateAssaySuggestions();

  // Synchronous validation for version
  function validateVersionSync() {
      let isValid = false;
      const xhr = new XMLHttpRequest();
      xhr.open('POST', validateVersionUrl, false); // Synchronous request
      xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.send(JSON.stringify({ value: versionField.value.trim() }));

      if (xhr.status === 200) {
          const response = JSON.parse(xhr.responseText);
          isValid = !response.exists;
          if (!isValid) {
              versionError.textContent = 'Version already exists or cannot be downgraded. Please use a new version.';
          } else {
              versionError.textContent = '';
          }
      }
      return isValid;
  }

  // Synchronous validation for name
  function validateNameSync() {
      let isValid = false;
      const xhr = new XMLHttpRequest();
      xhr.open('POST', validateNameUrl, false); // Synchronous request
      xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.send(JSON.stringify({ value: nameField.value.trim(), genepanel_id: panelId }));

      if (xhr.status === 200) {
          const response = JSON.parse(xhr.responseText);
          isValid = !response.exists;
          if (!isValid) {
              nameError.textContent = 'Name is already associated with another panel. Please use a different name.';
          } else {
              nameError.textContent = '';
          }
      }
      return isValid;
  }

  // Synchronous validation for display name
  function validateDisplayNameSync() {
      let isValid = false;
      const xhr = new XMLHttpRequest();
      xhr.open('POST', validateDisplayNameUrl, false); // Synchronous request
      xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.send(JSON.stringify({ value: displaynameField.value.trim(), genepanel_id: panelId }));

      if (xhr.status === 200) {
          const response = JSON.parse(xhr.responseText);
          isValid = !response.exists;
          if (!isValid) {
              displaynameError.textContent = 'Display name is already associated with another panel. Please use a different display name.';
          } else {
              displaynameError.textContent = '';
          }
      }
      return isValid;
  }

  // Attach validation to the blur events
  versionField.addEventListener('blur', validateVersionSync);
  nameField.addEventListener('blur', validateNameSync);
  displaynameField.addEventListener('blur', validateDisplayNameSync);

  // Form submission handler
  document.getElementById('genePanelForm').addEventListener('submit', function(event) {
      // Perform all validations synchronously
      const isVersionValid = validateVersionSync();
      const isNameValid = validateNameSync();
      const isDisplayNameValid = validateDisplayNameSync();

      // If any validation fails, prevent form submission
      if (!isVersionValid || !isNameValid || !isDisplayNameValid) {
          event.preventDefault();
          if (!isNameValid) nameField.focus();
          else if (!isDisplayNameValid) displaynameField.focus();
          else if (!isVersionValid) versionField.focus();
      }
  });
});
