
// Define a function encapsulating your code
// This function is used in the adduser setion of the admin.
function initializePhoneNumberVerification() {
  document.addEventListener('DOMContentLoaded', function () {
    const phoneInputField = document.querySelector("#phone");
    const phoneInput = window.intlTelInput(phoneInputField, {
      utilsScript: "https://cdnjs.cloudflare.com/ajax/libs/intl-tel-input/17.0.8/js/utils.js",
    });

    var saveButtons = document.querySelectorAll("input[type='submit']"); // Target all submit buttons

    // Function to disable save buttons
    function disableSaveButtons() {
      saveButtons.forEach(button => button.disabled = true);
    }

    // Initially disable save buttons on page load
    disableSaveButtons();

    var verifyButton = document.querySelector('#verify-button');
    var visiblePhoneNumberField = document.querySelector('#id_phone_number');
    verifyButton.addEventListener('click', function () {
      event.preventDefault();
      const phoneNumber = phoneInput.getNumber();
      console.log('Verify button clicked!');
      $("#phone_number").val(phoneNumber);

      var isValid = phoneInput.isValidNumber(); // Check if the phone number is valid

      if (isValid) {
        // Phone number is valid, proceed to check uniqueness

        var csrftoken = getCookie('csrftoken'); // Retrieving CSRF token

        // Perform AJAX request to check the uniqueness of the phone number
        $.ajax({
          url: checkPhoneNumberUniqueURL,
          type: 'POST',
          data: { 'phone_number': phoneNumber },
          headers: { 'X-CSRFToken': csrftoken },  // Include the CSRF token in the request headers
          success: function (response) {
            if (response.exists) {
              // Phone number is valid but not unique
              alert('This phone number is already in use');
              console.log("used");
              // Disable save buttons
              disableSaveButtons();
            } else {
              // Phone number is both valid and unique
              alert('This phone number is valid and unique');
              console.log("good");
              visiblePhoneNumberField.value = phoneNumber; // Set value
              visiblePhoneNumberField.setAttribute('readonly', true);
              // Enable save buttons
              saveButtons.forEach(button => button.disabled = false);
            }
          },
          error: function () {
            alert('Error checking phone number uniqueness');
            // Disable save buttons if there's an error
            disableSaveButtons();
          }
        });
      } else {
        // Phone number is not valid
        alert('Invalid phone number');
        // Disable save buttons if phone number is not valid
        disableSaveButtons();
      }
    });
  });

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
  }
}


