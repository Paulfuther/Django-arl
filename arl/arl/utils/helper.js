// helper.js

// Function to check phone number uniqueness
function checkPhoneNumberUnique(phoneNumber) {
    // Perform AJAX request to check the uniqueness of the phone number
    return new Promise((resolve, reject) => {
      const csrftoken = getCookie('csrftoken');
      $.ajax({
        url: '{% url 'check_phone_number_unique' %}',
        type: 'POST',
        data: { 'phone_number': phoneNumber },
        headers: { 'X-CSRFToken': csrftoken },
        success: function (response) {
          resolve(response.exists);
        },
        error: function () {
          reject('Error occurred while checking phone number uniqueness');
        }
      });
    });
  }
  
  // Function to request verification code from Twilio
  function requestVerificationCode(phoneNumber) {
    // Request verification code from Twilio
    return new Promise((resolve, reject) => {
      const csrftoken = getCookie('csrftoken');
      $.ajax({
        url: '/request-verification/',
        type: 'POST',
        data: { 'phone_number': phoneNumber },
        headers: { 'X-CSRFToken': csrftoken },
        success: function (response) {
          resolve(response.success);
        },
        error: function () {
          reject('Error occurred while requesting verification code');
        }
      });
    });
  }
  
  // Function to check the verification code
  function checkVerificationCode(phoneNumber, verificationCode) {
    // Send the verification code to the server for verification
    return new Promise((resolve, reject) => {
      const csrftoken = getCookie('csrftoken');
      $.ajax({
        url: '/check-verification/',
        type: 'POST',
        data: {
          'phone_number': phoneNumber,
          'verification_code': verificationCode
        },
        headers: { 'X-CSRFToken': csrftoken },
        success: function (response) {
          resolve(response.success);
        },
        error: function () {
          reject('Error occurred while checking verification code');
        }
      });
    });
  }
  
  // Export the functions
  export {
    checkPhoneNumberUnique,
    requestVerificationCode,
    checkVerificationCode
  };
  