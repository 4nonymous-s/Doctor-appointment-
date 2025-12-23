/* booking.js
   Handles booking modal open/close and booking POST.
   Depends on showNotification (defined in inline template script) for global notifications.
*/
(function(){
  const $ = id => document.getElementById(id);
  const bookingModal = $('bookingModal');
  const modalClose = $('modalClose');
  const cancelBooking = $('cancelBooking');
  const confirmBooking = $('confirmBooking');
  const modalDoctor = $('modalDoctor');
  const modalHospital = $('modalHospital');
  const apptDate = $('appt-date');
  const apptNote = $('appt-note');
  const modalNotif = $('modalNotif');
  let lastFocusedEl = null;

  // Open modal. We no longer require doctor_id or user_id for booking.
  // Provide docName (for display) and hospitalId (to send to the API).
  function openBookingModal(docName, hospitalId, hospitalName){
    lastFocusedEl = document.activeElement;
    bookingModal.setAttribute('aria-hidden','false');
    bookingModal.classList.add('open');
    modalDoctor.textContent = docName || 'Doctor';
    modalHospital.textContent = hospitalName || '';
    // store hospital id on confirm button
    confirmBooking.dataset.hospitalId = hospitalId;
    apptDate.value = '';
    apptNote.value = '';
    modalNotif.hidden = true;
    setTimeout(()=>{ apptDate.focus(); }, 120);
    document.addEventListener('keydown', trapModalKey);
  }

  function closeBookingModal(){
    bookingModal.setAttribute('aria-hidden','true');
    bookingModal.classList.remove('open');
    document.removeEventListener('keydown', trapModalKey);
    if(lastFocusedEl && lastFocusedEl.focus) lastFocusedEl.focus();
  }

  function trapModalKey(e){
    if(e.key === 'Escape'){ closeBookingModal(); }
    if(e.key === 'Tab'){
      const focusable = bookingModal.querySelectorAll('button, [href], input, textarea, select, [tabindex]:not([tabindex="-1"])');
      if(focusable.length===0) return;
      const first = focusable[0];
      const last = focusable[focusable.length-1];
      if(e.shiftKey && document.activeElement === first){ e.preventDefault(); last.focus(); }
      else if(!e.shiftKey && document.activeElement === last){ e.preventDefault(); first.focus(); }
    }
  }

  modalClose.addEventListener('click', closeBookingModal);
  if(cancelBooking) cancelBooking.addEventListener('click', closeBookingModal);

  confirmBooking.addEventListener('click', async function(){
    const hospitalId = this.dataset.hospitalId;
    const scheduled_at = apptDate.value;
    if(!scheduled_at){ modalNotif.hidden=false; modalNotif.textContent='Please choose date and time'; modalNotif.className='notification error'; return }
    try{
      // Require user to be logged in
      if(!window.currentUserId){
        modalNotif.hidden = false;
        modalNotif.className = 'notification error';
        modalNotif.textContent = 'Please register or log in before booking.';
        // if login modal is available, open it to help the user
        try{ if(typeof window.openLoginModal === 'function') window.openLoginModal(); }catch(e){}
        return;
      }

      this.disabled = true;
      modalNotif.hidden = false; modalNotif.textContent = 'Booking…'; modalNotif.className='notification info';
      // Send minimal payload: hospital_id, scheduled_at, and optional note; include user_id
      const payload = { scheduled_at, user_id: window.currentUserId };
      if(hospitalId) payload.hospital_id = hospitalId;
      if(apptNote.value) payload.note = apptNote.value;
      const resp = await fetch('/api/book', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
      const data = await resp.json();
      if(resp.ok){ modalNotif.className='notification success'; modalNotif.textContent = 'Booked — id: '+(data.appointment_id||data.id||'unknown'); if(typeof showNotification==='function') showNotification('Booking successful', 'success'); setTimeout(closeBookingModal, 1200); }
      else { modalNotif.className='notification error'; modalNotif.textContent = data.error || JSON.stringify(data); if(typeof showNotification==='function') showNotification(data.error || 'Booking failed', 'error'); }
    }catch(err){ modalNotif.className='notification error'; modalNotif.textContent = err.message || 'Booking failed'; if(typeof showNotification==='function') showNotification(err.message || 'Booking failed','error'); }
    finally{ this.disabled = false; }
  });

  // expose open function globally for other scripts
  window.openBookingModal = openBookingModal;
})();
