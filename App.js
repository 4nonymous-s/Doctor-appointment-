import React, {useState, useEffect, useRef} from 'react';

function App(){
  const [locality, setLocality] = useState('');
  const [hospitals, setHospitals] = useState([]);
  const [selectedHospital, setSelectedHospital] = useState(null);
  const [doctors, setDoctors] = useState([]);
  const [user, setUser] = useState(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingDoctors, setLoadingDoctors] = useState(false);
  const searchTimer = useRef(null);

  async function search(){
    try{
      setLoading(true);
      const resp = await fetch('/api/hospitals?locality='+encodeURIComponent(locality));
      if(!resp.ok) throw new Error('Search failed');
      const data = await resp.json();
      setHospitals(data);
    }catch(e){
      alert(e.message || 'Search failed');
    }finally{
      setLoading(false);
    }
  }

  async function viewDoctors(hospital){
    setSelectedHospital(hospital);
    setLoadingDoctors(true);
    try{
      const resp = await fetch('/api/hospital/'+hospital.id+'/doctors');
      if(!resp.ok) throw new Error('Failed to load doctors');
      const data = await resp.json();
      setDoctors(data);
    }catch(e){
      alert(e.message || 'Failed to load doctors');
    }finally{
      setLoadingDoctors(false);
    }
  }

  // Debounce search when typing locality
  useEffect(()=>{
    if(searchTimer.current) clearTimeout(searchTimer.current);
    if(locality && locality.trim().length>0){
      searchTimer.current = setTimeout(()=>{ search(); }, 600);
    }
    return ()=>{ if(searchTimer.current) clearTimeout(searchTimer.current); };
  }, [locality]);

  async function register(){
    try{
      const resp = await fetch('/api/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password,full_name:username})});
      const data = await resp.json();
      alert(JSON.stringify(data));
    }catch(e){ alert(e.message || 'Registration failed') }
  }

  async function login(){
    try{
      const resp = await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password})});
      const data = await resp.json();
      if(resp.ok){ setUser(data); alert('Logged in as '+data.username); } else { alert(JSON.stringify(data)); }
    }catch(e){ alert(e.message || 'Login failed') }
  }

  async function book(doctor){
    if(!selectedHospital){ alert('Select a hospital first'); return; }
    if(!confirm(`Book appointment with ${doctor.name}?`)) return;
    const dt = new Date().toISOString();
    try{
      // Send minimal payload: hospital_id and scheduled_at (user_id and doctor_id are not required)
      const resp = await fetch('/api/book',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({hospital_id:selectedHospital.id, scheduled_at:dt})});
      const data = await resp.json();
      if(resp.ok) alert('Booked — id:'+ (data.appointment_id || data.id || 'unknown'));
      else alert(JSON.stringify(data));
    }catch(e){ alert(e.message || 'Booking failed') }
  }

  return (<div style={{padding:20,fontFamily:'Inter, Arial, sans-serif'}}>
    <header style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:16}}>
      <h1 style={{margin:0}}>Hospital Appointment Finder</h1>
        <div style={{display:'flex',alignItems:'center',gap:10}}>
        <input aria-label="Locality" style={{padding:8,borderRadius:8,border:'1px solid #ddd'}} value={locality} onChange={e=>setLocality(e.target.value)} placeholder='Enter locality' onKeyDown={e=>{ if(e.key==='Enter'){ e.preventDefault(); search(); } }} />
        <button aria-label="Search hospitals" onClick={search} disabled={loading} aria-busy={loading} style={{padding:'8px 12px',borderRadius:8}}>{loading ? 'Searching…' : 'Search'}</button>
      </div>
    </header>

    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 280px',gap:20}}>
      <div>
        <h2 style={{marginTop:0}}>Hospitals <small style={{color:'#666',fontWeight:400}}>{hospitals.length ? `(${hospitals.length})` : ''}</small></h2>
        {hospitals.length===0 && <div style={{color:'#666'}}>No hospitals — try a different locality or clear the input.</div>}
        {hospitals.map(h=>(<div key={h.id} style={{border:'1px solid #eee',padding:12,marginBottom:8,borderRadius:8,display:'flex',justifyContent:'space-between',alignItems:'center'}}>
          <div>
            <strong>{h.name}</strong>
            <div style={{color:'#666',fontSize:13}}>{h.locality} · {h.address}</div>
          </div>
          <div style={{display:'flex',flexDirection:'column',gap:8}}>
            <button onClick={()=>viewDoctors(h)} style={{padding:'6px 10px',borderRadius:8}}>View</button>
            <a href={`/?hospital=${h.id}`} style={{textDecoration:'none'}}><button style={{padding:'6px 10px',borderRadius:8}}>Open</button></a>
          </div>
        </div>))}
      </div>

      <div>
        <h2 style={{marginTop:0}}>Doctors {selectedHospital && ` — ${selectedHospital.name}`}</h2>
        {loadingDoctors && <div style={{color:'#666'}}>Loading doctors…</div>}
        {!loadingDoctors && doctors.length===0 && <div style={{color:'#666'}}>No doctors to show.</div>}
        {doctors.map(d=>(<div key={d.id} style={{border:'1px solid #eee',padding:12,marginBottom:8,borderRadius:8}}>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
            <div>
              <strong>{d.name}</strong>
              <div style={{color:'#666',fontSize:13}}>{d.specialty} — Ward: {d.ward || '—'}</div>
              <div style={{marginTop:6,fontSize:13,color:'#666'}}>{d.qualification ? d.qualification : ''}{d.qualification && d.experience_years ? ' · ' : ''}{d.experience_years ? d.experience_years + ' yrs exp' : ''}</div>
              <div style={{marginTop:6,fontSize:13,color:'#666'}}>{d.email ? '✉ ' + d.email : ''}{d.email && d.phone ? ' · ' : ''}{d.phone ? '☎ ' + d.phone : ''}</div>
            </div>
            <div style={{textAlign:'right'}}>
              <div style={{fontWeight:700,color:d.is_available ? '#0b8a3e' : '#c0392b'}}>{d.is_available ? 'Available' : 'Unavailable'}</div>
              <button onClick={()=>book(d)} style={{marginTop:8,padding:'6px 10px',borderRadius:8}} disabled={!d.is_available}>Book</button>
            </div>
          </div>
        </div>))}
      </div>

      <aside style={{padding:12,border:'1px solid #eee',borderRadius:8}}>
        <h3 style={{marginTop:0}}>Account</h3>
        {!user ? (
          <div>
            <input placeholder='username' value={username} onChange={e=>setUsername(e.target.value)} style={{width:'100%',padding:8,borderRadius:6,border:'1px solid #ddd',marginBottom:8}} />
            <input placeholder='password' type='password' value={password} onChange={e=>setPassword(e.target.value)} style={{width:'100%',padding:8,borderRadius:6,border:'1px solid #ddd',marginBottom:8}} />
            <div style={{display:'flex',gap:8}}>
              <button onClick={register} style={{flex:1}}>Register</button>
              <button onClick={login} style={{flex:1}}>Login</button>
            </div>
          </div>
        ) : (
          <div>
            <div>Welcome <strong>{user.username}</strong></div>
            <div style={{marginTop:8}}><button onClick={()=>setUser(null)}>Logout</button></div>
          </div>
        )}
      </aside>
    </div>
  </div>);
}

export default App;
