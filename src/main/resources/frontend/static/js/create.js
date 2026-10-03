/* ============================================================
   FLEXY - Create Auction Page JS (create.js)
   ============================================================ */

(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {

    /* ── Live preview update ── */
    var titleInput    = document.getElementById('auctionTitle');
    var startBidInput = document.getElementById('startBid');
    var durationInput = document.getElementById('auctionDuration');
    var previewBid    = document.getElementById('previewBid');
    var previewDur    = document.getElementById('previewDur');
    var previewTitle  = document.getElementById('previewTitle');

    function updatePreview() {
      if (previewBid && startBidInput && startBidInput.value) {
        previewBid.textContent = '$' + parseFloat(startBidInput.value).toLocaleString();
      } else if (previewBid) {
        previewBid.textContent = '-- --';
      }
      if (previewDur && durationInput && durationInput.value) {
        previewDur.textContent = durationInput.value + ' days';
      } else if (previewDur) {
        previewDur.textContent = '-- days';
      }
      if (previewTitle && titleInput && titleInput.value) {
        var skeleton = document.getElementById('previewTitleSkeleton');
        if (skeleton) {
          skeleton.style.display = 'none';
          previewTitle.textContent = titleInput.value;
          previewTitle.style.display = 'block';
        }
      }
    }

    if (titleInput)    titleInput.addEventListener('input', updatePreview);
    if (startBidInput) startBidInput.addEventListener('input', updatePreview);
    if (durationInput) durationInput.addEventListener('change', updatePreview);

    /* ── Gallery upload (placeholder) ── */
    var uploadSlot = document.getElementById('uploadSlot');
    var fileInput  = document.getElementById('galleryFileInput');
    if (uploadSlot && fileInput) {
      uploadSlot.addEventListener('click', function () { fileInput.click(); });
      fileInput.addEventListener('change', function () {
        var file = fileInput.files[0];
        if (!file) return;
        var reader = new FileReader();
        reader.onload = function (e) {
          var img = document.createElement('img');
          img.src = e.target.result;
          img.style.cssText = 'width:100%;height:100%;object-fit:cover;';
          uploadSlot.innerHTML = '';
          uploadSlot.appendChild(img);
          uploadSlot.style.border = 'none';
        };
        reader.readAsDataURL(file);
      });
    }

    /* ── Progress steps ── */
    var steps = document.querySelectorAll('.progress-step');

    /* ── Continue button → next step / navigate ── */
    var continueBtn = document.getElementById('continueBtn');
    if (continueBtn) {
      var currentStep = 0;
      continueBtn.addEventListener('click', function () {
        var titleVal = titleInput ? titleInput.value.trim() : '';
        if (currentStep === 0 && !titleVal) {
          titleInput.style.boxShadow = '0 0 0 1px rgba(255,110,132,0.6)';
          titleInput.focus();
          return;
        }
        currentStep++;
        if (currentStep < steps.length) {
          steps.forEach(function (s, i) {
            if (i <= currentStep) s.classList.add('active');
            else s.classList.remove('active');
          });
          if (currentStep === steps.length - 1) {
            continueBtn.textContent = 'Publish Auction';
          }
        } else {
          // Final submit
          continueBtn.textContent = 'Publishing...';
          continueBtn.disabled = true;
          setTimeout(function () {
            window.location.href = 'dashboard.html';
          }, 1500);
        }
      });
    }

    /* ── Save as Draft ── */
    var draftBtn = document.getElementById('draftBtn');
    if (draftBtn) {
      draftBtn.addEventListener('click', function () {
        draftBtn.textContent = 'Draft Saved ✓';
        setTimeout(function () { draftBtn.textContent = 'Save as Draft'; }, 2000);
      });
    }

    /* ── Character counter for description ── */
    var descTextarea = document.getElementById('auctionDesc');
    var descCounter  = document.getElementById('descCounter');
    if (descTextarea && descCounter) {
      descTextarea.addEventListener('input', function () {
        descCounter.textContent = descTextarea.value.length + ' / 500';
      });
    }
  });
})();
