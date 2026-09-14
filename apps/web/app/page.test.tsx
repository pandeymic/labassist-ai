import '@testing-library/jest-dom'; import {render,screen} from '@testing-library/react'; import Home from './page';
global.fetch=jest.fn().mockImplementation((url:string)=>Promise.resolve({json:async()=>url.includes('auth')?{token:'demo'}:url.includes('appointments')?{data:[]}:{data:[]}})) as jest.Mock;
test('shows demo safety label after loading',async()=>{render(<Home/>); expect(await screen.findByText(/synthetic records only/i)).toBeInTheDocument();});
