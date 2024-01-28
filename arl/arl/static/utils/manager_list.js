function initializeManagerDropdown() {
    var employerSelect = document.getElementById('id_employer');
    var managerDropdown = document.getElementById('id_manager_dropdown');

    // Function to update the manager dropdown
    function updateManagerDropdown(dropdown, managerData,) {
        // Remove existing options
        while (dropdown.options.length > 0) {
            dropdown.remove(0);
        }

        // Add a default option
        var defaultOption = document.createElement('option');
        defaultOption.text = 'Select a manager';
        defaultOption.value = '';
        dropdown.add(defaultOption);

        // Populate the dropdown with manager names
        managerData.forEach(function (manager) {
            var option = document.createElement('option');
            option.value = manager.id;
            option.text = manager.username;
            dropdown.add(option);
        });
    }

    // Add an event listener to the employer dropdown
    employerSelect.addEventListener('change', function () {
        var employerId = employerSelect.value;

        if (!employerId) {
            // If no employer is selected, reset the manager dropdown
            updateManagerDropdown(managerDropdown, []);
            
            return;
        }

        // Make an AJAX request to fetch managers for the selected employer
        fetch('/fetch_managers/?employer=' + employerId)
            .then(response => response.json())
            .then(data => {
                // Update the manager dropdown with the fetched data
                updateManagerDropdown(managerDropdown, data);
            })
            .catch(error => console.error('Error:', error));
    });

    // Initial update when the page loads
    updateManagerDropdown(managerDropdown, []);
}

// Call the function to initialize the manager dropdown
 initializeManagerDropdown();
