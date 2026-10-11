import { test, expect } from './fixtures';
test('Scribe SDK receives editable text and releases simulated microphone tracks on stop, cancel, and close',async({page})=>{
  await page.route('**/api/config',route=>route.fulfill({json:{browserKey:'',mapId:'',routes:false,voice:true,authenticated:true,localDemo:true}}));
  let tokens=0;await page.route('**/api/scribe-token',route=>{tokens++;return route.fulfill({json:{token:`test-token-${tokens}`}});});
  await page.addInitScript(()=>{
    (window as any).__stoppedTracks=0;
    Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:async()=>{const context=new AudioContext(),destination=context.createMediaStreamDestination(),track=destination.stream.getAudioTracks()[0],stop=track.stop.bind(track);track.stop=()=>{(window as any).__stoppedTracks++;stop();void context.close();};return destination.stream;}});
  });
  await page.routeWebSocket('wss://api.elevenlabs.io/**',socket=>{setTimeout(()=>socket.send(JSON.stringify({message_type:'session_started',session_id:'test-session'})),100);setTimeout(()=>socket.send(JSON.stringify({message_type:'committed_transcript',text:'Open the Oak Lane job.'})),200);});
  await page.goto('/');await page.getByRole('button',{name:'Voice or type commands'}).click();
  await page.getByRole('button',{name:'Start microphone'}).click();await expect(page.locator('.voice-phase')).toContainText('Listening');await expect(page.getByLabel('Editable command')).toHaveValue('Open the Oak Lane job.');
  await page.getByRole('button',{name:'Stop',exact:true}).click();await expect.poll(()=>page.evaluate(()=>(window as any).__stoppedTracks)).toBe(1);await page.getByLabel('Editable command').fill('Show available plumbers.');await page.getByRole('button',{name:'Run command'}).click();await expect(page.locator('.command-feedback')).toContainText('Showing available plumbing technicians');
  await page.getByRole('button',{name:'Start microphone'}).click();await expect(page.locator('.voice-phase')).toContainText('Listening');await page.getByRole('button',{name:'Cancel',exact:true}).click();await expect(page.getByLabel('Editable command')).toHaveValue('');await expect.poll(()=>page.evaluate(()=>(window as any).__stoppedTracks)).toBe(2);
  await page.getByRole('button',{name:'Start microphone'}).click();await expect(page.locator('.voice-phase')).toContainText('Listening');await page.getByRole('button',{name:'Close dialog'}).click();await expect.poll(()=>page.evaluate(()=>(window as any).__stoppedTracks)).toBe(3);expect(tokens).toBe(3);
});
