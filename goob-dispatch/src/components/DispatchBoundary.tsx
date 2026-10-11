import {Component,type ReactNode} from 'react';
export class DispatchBoundary extends Component<{children:ReactNode;map?:boolean},{failed:boolean}>{
 state={failed:false};
 static getDerivedStateFromError(){return {failed:true};}
 render(){return this.state.failed?<section className={this.props.map?'map-card':'operations-page'} role="alert"><p>{this.props.map?'Map unavailable. Job details and actions remain available.':'Dispatch could not render this view. Your records are unchanged.'}</p><button onClick={()=>this.setState({failed:false})}>Retry view</button></section>:this.props.children;}
}
