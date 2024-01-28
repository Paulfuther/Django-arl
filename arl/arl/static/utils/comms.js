// Function to initialize tab functionality
function initTabs() {
    // Initial setup
    $("input[name='tab']:first").prop("checked", true);
    loadForm($("input[name='tab']:checked").data("form-url"));
  
    // Switching between tabs
    $("input[name='tab']").on("change", function () {
        var formUrl = $(this).data("form-url");
        loadForm(formUrl);
    });
  
    function loadForm(url) {
        $.ajax({
            url: url,
            method: "GET",
            success: function (response) {
                $("#form-container").html(response);
            },
            error: function (xhr, status, error) {
                console.error("Error loading form:", status, error);
            }
        });
    }
  }