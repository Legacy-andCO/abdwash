// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
const mfa=vi.hoisted(()=>({listFactors:vi.fn(),enroll:vi.fn(),unenroll:vi.fn(),challengeAndVerify:vi.fn()}));
vi.mock("../lib",()=>({supabase:{auth:{mfa,signOut:vi.fn()}}}));
vi.mock("react-native",()=>({ScrollView:({children}:any)=><div>{children}</div>,View:({children}:any)=><div>{children}</div>,Text:({children}:any)=><span>{children}</span>,TextInput:({onChangeText,accessibilityLabel,...props}:any)=><input aria-label={accessibilityLabel} onChange={e=>onChangeText(e.target.value)} {...props}/>}));
vi.mock("react-native-svg",()=>({SvgXml:({xml}:any)=><div data-testid="qr">{xml}</div>}));
vi.mock("./ui",()=>({AppButton:({title,onPress,disabled}:any)=><button disabled={disabled} onClick={onPress}>{title}</button>}));
import { PrivilegedMfa } from "./PrivilegedMfa";
afterEach(()=>{cleanup();vi.resetAllMocks();});
it("shows native enrollment QR and grants access only after provider verification",async()=>{
 mfa.listFactors.mockResolvedValue({data:{totp:[],all:[]}});
 mfa.enroll.mockResolvedValue({data:{id:"synthetic-factor",totp:{qr_code:"data:image/svg+xml,%3Csvg%3Etest%3C%2Fsvg%3E"}}});
 mfa.challengeAndVerify.mockResolvedValueOnce({error:new Error("invalid")}).mockResolvedValueOnce({data:{}});
 const done=vi.fn();render(<PrivilegedMfa onVerified={done}/>);
 await waitFor(()=>expect(screen.getByTestId("qr").textContent).toContain("<svg>"));
 fireEvent.change(screen.getByLabelText("Authenticator code"),{target:{value:"123456"}});fireEvent.click(screen.getByText("Verify authenticator"));
 await screen.findByText(/rejected or expired/);expect(done).not.toHaveBeenCalled();
 fireEvent.change(screen.getByLabelText("Authenticator code"),{target:{value:"654321"}});fireEvent.click(screen.getByText("Verify authenticator"));
 await waitFor(()=>expect(done).toHaveBeenCalledOnce());expect(mfa.challengeAndVerify).toHaveBeenLastCalledWith({factorId:"synthetic-factor",code:"654321"});
});
it("challenges an existing verified factor without reenrolling or removing it",async()=>{
 mfa.listFactors.mockResolvedValue({data:{totp:[{id:"existing",status:"verified"}],all:[]}});
 render(<PrivilegedMfa onVerified={vi.fn()}/>);await screen.findByText(/Enter your authenticator code/);
 expect(mfa.enroll).not.toHaveBeenCalled();expect(mfa.unenroll).not.toHaveBeenCalled();
});
