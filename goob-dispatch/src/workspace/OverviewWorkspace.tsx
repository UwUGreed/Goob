import { useEffect, type ReactNode } from 'react';
import type { Preferences } from '../types';
import type { Account } from './config';
import { useWorkspace } from './useWorkspace';
import { WorkspaceToolbar, WorkspaceGrid, WorkspaceEditor } from './WorkspaceEditor';

export function OverviewWorkspace({account,render}:{account:Account;render:(preferences:Preferences)=>Record<string,ReactNode>}) {
 const workspace=useWorkspace('overview',account);
 useEffect(()=>{const open=()=>workspace.begin();window.addEventListener('goob-customize-workspace',open);return()=>window.removeEventListener('goob-customize-workspace',open);},[workspace.begin]);
 return <div className={`overview-workspace density-${workspace.configuration.preferences.density}`}><WorkspaceToolbar workspace={workspace}/><WorkspaceEditor workspace={workspace} account={account}/><WorkspaceGrid workspace={workspace}>{render(workspace.configuration.preferences)}</WorkspaceGrid></div>;
}
