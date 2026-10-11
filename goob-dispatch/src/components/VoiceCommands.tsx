import { useEffect, useRef, useState } from 'react';
import { useScribe, CommitStrategy } from '@elevenlabs/react';
import { Mic, Square, X, ArrowRight, Volume2 } from 'lucide-react';
import { Dialog } from './Dialog';
import { api, type IntegrationConfig } from '../integrations/api';
export type CommandFeedback={message:string;ok?:boolean;spoken?:string;choices?:{label:string;text:string}[]};
export default function VoiceCommands({config,onClose,onCommand,initialDraft=''}:{initialDraft?:string;config:IntegrationConfig;onClose:()=>void;onCommand:(text:string)=>CommandFeedback}){
  const [phase,setPhase]=useState<'Disconnected'|'Processing'|'Listening'|'Transcribing'|'Success'|'Error'>('Disconnected'),[draft,setDraft]=useState(initialDraft),[message,setMessage]=useState('Type a command, or start the microphone.'),[choices,setChoices]=useState<CommandFeedback['choices']>([]);
  const active=useRef(false),generation=useRef(0),tokenRequest=useRef<AbortController|null>(null),committed=useRef(''),partial=useRef(''),timer=useRef<ReturnType<typeof setTimeout>|null>(null),sdk=useRef<()=>void>(()=>{});
  const [speaking,setSpeaking]=useState(false),reply=useRef(''),utterance=useRef<SpeechSynthesisUtterance|null>(null);
  const canSpeak=typeof window.speechSynthesis!=='undefined'&&typeof SpeechSynthesisUtterance!=='undefined';
  function stopSpeaking(){if(utterance.current){utterance.current.onend=null;utterance.current.onerror=null;window.speechSynthesis.cancel();utterance.current=null;}setSpeaking(false);}
  function speak(text:string){stopSpeaking();reply.current=text;if(!canSpeak)return;const speech=new SpeechSynthesisUtterance(text);speech.lang='en-US';speech.rate=1;utterance.current=speech;setSpeaking(true);speech.onend=speech.onerror=()=>{utterance.current=null;setSpeaking(false);};window.speechSynthesis.speak(speech);}
  function clearTimer(){if(timer.current)clearTimeout(timer.current);timer.current=null;}
  function disconnect(){active.current=false;generation.current++;tokenRequest.current?.abort();tokenRequest.current=null;clearTimer();sdk.current();}
  function fail(message:string){disconnect();setPhase('Error');setMessage(message);}
  const scribe=useScribe({modelId:'scribe_v2_realtime',commitStrategy:CommitStrategy.VAD,languageCode:'en',vadSilenceThresholdSecs:.7,enableLogging:false,
    onSessionStarted:()=>{if(!active.current)return;clearTimer();setPhase('Listening');setMessage('Listening. Stop to review and edit your transcript.');timer.current=setTimeout(()=>stop(),60000);},
    onPartialTranscript:({text})=>{if(!active.current)return;setPhase('Transcribing');partial.current=text;setDraft([committed.current,partial.current].filter(Boolean).join(' '));},
    onCommittedTranscript:({text})=>{if(!active.current)return;setPhase('Listening');committed.current=[committed.current,text].filter(Boolean).join(' ');partial.current='';setDraft(committed.current);},
    onError:(error)=>{if(!active.current)return;const text=error instanceof Error?error.message:'';fail(/denied|notallowed|permission/i.test(text)?'Microphone permission was denied. Allow access in your browser, or type a command.':'Transcription disconnected or failed. Check microphone permission, connectivity, and ElevenLabs configuration. Typed commands remain available.');},
  });sdk.current=scribe.disconnect;
  useEffect(()=>()=>{disconnect();if(utterance.current){utterance.current.onend=null;utterance.current.onerror=null;window.speechSynthesis.cancel();}},[]);
  useEffect(()=>{if(active.current&&scribe.status==='disconnected'&&(phase==='Listening'||phase==='Transcribing')){disconnect();setPhase('Disconnected');setMessage('Microphone disconnected. Your current transcript is available to edit.');}},[scribe.status]);
  async function start(){
    if(active.current)return;
    stopSpeaking();
    if(!config.voice){fail('Voice is not configured on this server. Use a typed command.');return;}
    if(!config.authenticated){fail('Sign in to use the microphone. Typed commands remain available.');return;}
    if(!window.isSecureContext||!navigator.mediaDevices?.getUserMedia){fail('Microphone access needs HTTPS and a supported browser. Use a typed command.');return;}
    active.current=true;const version=++generation.current;committed.current='';partial.current='';setDraft('');setChoices([]);setPhase('Processing');setMessage('Connecting to ElevenLabs Scribe…');scribe.clearTranscripts();const abort=new AbortController();tokenRequest.current=abort;
    timer.current=setTimeout(()=>fail('Microphone connection timed out. Check permission and try again, or type a command.'),20000);
    try{const {token}=await api<{token:string}>('/api/scribe-token',{},abort.signal);if(!active.current||version!==generation.current)return;await scribe.connect({token,microphone:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});if(!active.current||version!==generation.current)scribe.disconnect();}
    catch(error){if(version!==generation.current||abort.signal.aborted)return;const message=error instanceof Error?error.message:'Microphone connection failed.';fail(/denied|notallowed|permission/i.test(message)?'Microphone permission was denied. Type a command or allow microphone access.':message);}
  }
  function stop(){const text=[committed.current,partial.current].filter(Boolean).join(' ');disconnect();setDraft(text);setPhase('Disconnected');setMessage('Microphone stopped. Review the transcript, then run the command.');}
  function cancel(){disconnect();stopSpeaking();reply.current='';committed.current='';partial.current='';setDraft('');setChoices([]);setPhase('Disconnected');setMessage('Recording canceled. No command was run.');}
  async function run(text=draft){if(active.current||!text.trim())return;stopSpeaking();reply.current='';setPhase('Processing');await new Promise<void>(resolve=>requestAnimationFrame(()=>resolve()));const feedback=onCommand(text);setMessage(feedback.message);setChoices(feedback.choices);setPhase(feedback.ok===false?'Error':'Success');if(feedback.spoken)speak(feedback.spoken);}
  return <Dialog title="Ask Goob" onClose={onClose}><p className="dialog-description">Speak or type your request. Review the recommendation, then confirm the assignment in the job panel.</p>
    <div className={`voice-phase phase-${phase.toLowerCase()}`} role="status"><span/>{phase}<small>{config.voice?'ElevenLabs Scribe realtime':'Typed commands · Microphone not configured'}</small></div>
    <label className="transcript-label" htmlFor="dispatch-transcript">Editable command</label><textarea id="dispatch-transcript" value={draft} readOnly={active.current} onChange={e=>{setDraft(e.target.value);setChoices([]);}} placeholder="Find an available plumber for Oak Lane and check parts readiness." rows={4}/>
    <p className="command-feedback" role={phase==='Error'?'alert':'status'}>{message}</p>
    <div className="spoken-reply"><Volume2 size={15}/><span>{canSpeak?'Availability answers are spoken using your browser voice.':'Browser voice is unavailable; answers appear above.'}</span>{reply.current&&canSpeak&&<button onClick={()=>speaking?stopSpeaking():speak(reply.current)}>{speaking?'Stop reply':'Replay reply'}</button>}</div>
    <div className="voice-actions"><button className="secondary-button" onClick={start} disabled={active.current}><Mic size={16}/> Start microphone</button><button className="secondary-button" onClick={stop} disabled={!active.current}><Square size={14}/> Stop</button><button className="secondary-button" onClick={cancel}><X size={15}/> Cancel</button></div>
    <button className="primary-button run-command" onClick={()=>run()} disabled={active.current||!draft.trim()}>Run command <ArrowRight size={16}/></button>
    {choices?.length?<div className="command-examples"><strong>Choose a record</strong>{choices.map(choice=><button key={choice.text} onClick={()=>{setDraft(choice.text);run(choice.text);}}>{choice.label}</button>)}</div>:<div className="command-examples"><strong>Try a typed command</strong>{['Who is available for electrical?','Show available plumbers.','Open the Oak Lane job.','Check parts for this visit.','Find the best technician for this job.','Preview Maya’s route.','Switch to 3D.','Follow Maya.'].map(example=><button key={example} onClick={()=>setDraft(example)} disabled={active.current}>{example}</button>)}</div>}
    <p className="voice-privacy">Microphone audio is sent to ElevenLabs only while you record. Goob does not save audio or transcripts.</p>
  </Dialog>;
}
