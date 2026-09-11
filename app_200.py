from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from app_100 import BG, BLUE, GREEN, ORANGE, PANEL, PURPLE, RED, TEAL, TEXT, PayCheck100App
from budget_200 import (
    category_limit_status,
    dashboard_200,
    delete_goal,
    delete_wallet,
    detect_duplicate_transactions,
    goal_overview,
    load_goals,
    load_limits,
    load_wallets,
    next_month_forecast,
    obligations_overview,
    payment_calendar,
    save_goal,
    save_wallet,
    set_limit,
    spending_anomalies,
    wallet_summary,
)
from history_store import load_history


class TableWindow(tk.Toplevel):
    def __init__(self, parent, title: str, columns: list[tuple[str, str, int]], rows: list[tuple]):
        super().__init__(parent)
        self.title(title)
        self.geometry("1120x660")
        self.minsize(840, 480)
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text=title, font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(0, 10))
        keys = tuple(key for key, _label, _width in columns)
        tree = ttk.Treeview(root, columns=keys, show="headings")
        for key, label, width in columns:
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor="w")
        for values in rows:
            tree.insert("", "end", values=values)
        scroll = ttk.Scrollbar(root, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")


class GoalEditor(tk.Toplevel):
    def __init__(self, parent: "GoalsWindow", row: dict | None = None):
        super().__init__(parent)
        self.parent = parent
        self.row = dict(row or {})
        self.title("Edytuj cel" if row else "Dodaj cel")
        self.resizable(False, False)
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        self.name = tk.StringVar(value=self.row.get("name", ""))
        self.target = tk.StringVar(value=str(self.row.get("target", "")))
        self.saved = tk.StringVar(value=str(self.row.get("saved", 0)))
        self.deadline = tk.StringVar(value=str(self.row.get("deadline", "")))
        for idx, (label, var) in enumerate((("Cel", self.name), ("Kwota docelowa", self.target), ("Już odłożono", self.saved), ("Termin YYYY-MM-DD", self.deadline))):
            ttk.Label(frame, text=label + ":").grid(row=idx, column=0, sticky="w", pady=4)
            ttk.Entry(frame, textvariable=var, width=32).grid(row=idx, column=1, padx=(10, 0), pady=4)
        ttk.Button(frame, text="Zapisz", command=self._save).grid(row=4, column=0, columnspan=2, pady=(12, 0))

    def _save(self):
        try:
            payload = dict(self.row)
            payload.update({"name": self.name.get().strip(), "target": float(self.target.get().replace(",", ".")), "saved": float(self.saved.get().replace(",", ".") or 0), "deadline": self.deadline.get().strip(), "active": True})
            save_goal(payload)
        except Exception as exc:
            messagebox.showerror("Cel", str(exc), parent=self)
            return
        self.parent.refresh()
        self.parent.app._refresh_200()
        self.destroy()


class GoalsWindow(tk.Toplevel):
    def __init__(self, app: "PayCheck200App"):
        super().__init__(app)
        self.app = app
        self.title("Cele i oszczędności")
        self.geometry("980x600")
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="Cele i oszczędności", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(root, text="Ustal cel, termin i aktualną kwotę. PayCheck policzy, ile trzeba odkładać miesięcznie.").pack(anchor="w", pady=(0, 10))
        cols = ("name", "target", "saved", "missing", "progress", "deadline", "monthly")
        self.tree = ttk.Treeview(root, columns=cols, show="headings")
        heads = {"name":"Cel","target":"Cel kwotowy","saved":"Odłożono","missing":"Brakuje","progress":"Postęp","deadline":"Termin","monthly":"Miesięcznie"}
        widths = {"name":180,"target":110,"saved":110,"missing":110,"progress":90,"deadline":110,"monthly":120}
        for key in cols:
            self.tree.heading(key, text=heads[key]); self.tree.column(key, width=widths[key], anchor="w")
        self.tree.pack(fill="both", expand=True)
        bar = ttk.Frame(root); bar.pack(fill="x", pady=(10,0))
        ttk.Button(bar, text="+ Dodaj cel", command=lambda: GoalEditor(self)).pack(side="left")
        ttk.Button(bar, text="Edytuj", command=self._edit).pack(side="left", padx=6)
        ttk.Button(bar, text="Usuń", command=self._delete).pack(side="left")
        self.refresh()

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Cele", "Zaznacz cel.", parent=self); return None
        return next((r for r in load_goals() if r.get("id") == sel[0]), None)

    def _edit(self):
        row = self._selected()
        if row: GoalEditor(self, row)

    def _delete(self):
        row = self._selected()
        if row and messagebox.askyesno("Cele", f"Usunąć cel: {row.get('name','')}?", parent=self):
            delete_goal(row["id"]); self.refresh(); self.app._refresh_200()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for row in goal_overview():
            monthly = "—" if row.get("monthly_needed") is None else f"{row['monthly_needed']:.2f} zł"
            self.tree.insert("", "end", iid=row["id"], values=(row["name"], f"{row['target']:.2f} zł", f"{row['saved']:.2f} zł", f"{row['missing']:.2f} zł", f"{row['progress']:.1f}%", row.get("deadline") or "—", monthly))


class WalletEditor(tk.Toplevel):
    def __init__(self, parent: "WalletsWindow", row: dict | None = None):
        super().__init__(parent)
        self.parent = parent; self.row = dict(row or {})
        self.title("Edytuj konto" if row else "Dodaj konto")
        self.resizable(False, False)
        frame = ttk.Frame(self, padding=16); frame.pack(fill="both", expand=True)
        self.name = tk.StringVar(value=self.row.get("name", "")); self.bank = tk.StringVar(value=self.row.get("bank", "")); self.balance = tk.StringVar(value=str(self.row.get("balance", 0)))
        for idx,(label,var) in enumerate((("Nazwa konta",self.name),("Bank",self.bank),("Saldo",self.balance))):
            ttk.Label(frame,text=label+":").grid(row=idx,column=0,sticky="w",pady=4); ttk.Entry(frame,textvariable=var,width=32).grid(row=idx,column=1,padx=(10,0),pady=4)
        ttk.Button(frame,text="Zapisz",command=self._save).grid(row=3,column=0,columnspan=2,pady=(12,0))

    def _save(self):
        try:
            payload=dict(self.row); payload.update({"name":self.name.get().strip(),"bank":self.bank.get().strip(),"balance":float(self.balance.get().replace(",",".") or 0),"active":True}); save_wallet(payload)
        except Exception as exc:
            messagebox.showerror("Konto",str(exc),parent=self); return
        self.parent.refresh(); self.parent.app._refresh_200(); self.destroy()


class WalletsWindow(tk.Toplevel):
    def __init__(self, app: "PayCheck200App"):
        super().__init__(app); self.app=app; self.title("Konta i banki"); self.geometry("980x590")
        root=ttk.Frame(self,padding=14); root.pack(fill="both",expand=True)
        ttk.Label(root,text="Konta i banki",font=("Segoe UI",18,"bold")).pack(anchor="w")
        ttk.Label(root,text="Saldo wpisujesz ręcznie; wpływy i wydatki miesięczne są liczone z zaimportowanych wyciągów.").pack(anchor="w",pady=(0,10))
        cols=("name","bank","balance","income","expenses","change"); self.tree=ttk.Treeview(root,columns=cols,show="headings")
        heads={"name":"Konto","bank":"Bank","balance":"Saldo","income":"Wpływy mies.","expenses":"Wydatki mies.","change":"Zmiana mies."}; widths={k:150 for k in cols}
        for key in cols:self.tree.heading(key,text=heads[key]);self.tree.column(key,width=widths[key],anchor="w")
        self.tree.pack(fill="both",expand=True)
        bar=ttk.Frame(root);bar.pack(fill="x",pady=(10,0));ttk.Button(bar,text="+ Dodaj konto",command=lambda:WalletEditor(self)).pack(side="left");ttk.Button(bar,text="Edytuj",command=self._edit).pack(side="left",padx=6);ttk.Button(bar,text="Usuń",command=self._delete).pack(side="left")
        self.refresh()

    def _selected(self):
        sel=self.tree.selection()
        if not sel: messagebox.showinfo("Konta","Zaznacz konto.",parent=self); return None
        return next((r for r in load_wallets() if r.get("id")==sel[0]),None)

    def _edit(self):
        row=self._selected()
        if row: WalletEditor(self,row)

    def _delete(self):
        row=self._selected()
        if row and messagebox.askyesno("Konta",f"Usunąć konto: {row.get('name','')}?",parent=self): delete_wallet(row["id"]);self.refresh();self.app._refresh_200()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for row in wallet_summary(self.app.transactions):
            self.tree.insert("","end",iid=row["id"],values=(row["name"],row.get("bank",""),f"{row['balance']:.2f} zł",f"{row['income']:.2f} zł",f"{row['expenses']:.2f} zł",f"{row['month_change']:+.2f} zł"))


class PayCheck200App(PayCheck100App):
    def __init__(self) -> None:
        super().__init__()
        self.title("PayCheck 2.0.0 — Menedżer budżetu domowego")
        self.geometry("1480x900")
        self._build_200_actions()
        self._build_200_menu()
        self._refresh_200()

    def _build_200_actions(self):
        parent=self.quick_frame
        self._action_button(parent,"Kalendarz",ORANGE,self._show_calendar).pack(side="left",padx=(7,0))
        self._action_button(parent,"Cele","#2F7D63",self._show_goals).pack(side="left",padx=(7,0))
        self._action_button(parent,"Limity","#8C6D1F",self._show_limits).pack(side="left",padx=(7,0))
        self._action_button(parent,"Konta",BLUE,self._show_wallets).pack(side="left",padx=(7,0))

    def _build_200_menu(self):
        menu=tk.Menu(self)
        home=tk.Menu(menu,tearoff=False);home.add_command(label="Dashboard",command=self._refresh_200);home.add_command(label="Dodaj / aktualizuj wyciąg",command=self._add_statements);home.add_command(label="Do zatwierdzenia",command=self._review_center_060);menu.add_cascade(label="Start",menu=home)
        budget=tk.Menu(menu,tearoff=False);budget.add_command(label="Zarządzanie budżetem",command=self._show_budget_manager);budget.add_command(label="Kalendarz płatności",command=self._show_calendar);budget.add_command(label="Limity kategorii",command=self._show_limits);budget.add_command(label="Cele i oszczędności",command=self._show_goals);menu.add_cascade(label="Budżet",menu=budget)
        money=tk.Menu(menu,tearoff=False);money.add_command(label="Konta i banki",command=self._show_wallets);money.add_command(label="Raty i zobowiązania",command=self._show_installment_manager);money.add_command(label="Centrum zobowiązań",command=self._show_obligations);menu.add_cascade(label="Finanse",menu=money)
        intelligence=tk.Menu(menu,tearoff=False);intelligence.add_command(label="Prognoza następnego miesiąca",command=self._show_next_forecast);intelligence.add_command(label="Anomalie i duplikaty",command=self._show_intelligence);intelligence.add_command(label="Historia i trendy",command=self._show_history);menu.add_cascade(label="Analiza",menu=intelligence)
        settings=tk.Menu(menu,tearoff=False);settings.add_command(label="Zasady BLIK / przelew / karta",command=self._show_payment_policy);settings.add_command(label="Tolerancje dopasowania",command=self._show_match_settings);settings.add_separator();settings.add_command(label="Eksportuj backup",command=self._export_backup);settings.add_command(label="Importuj backup",command=self._import_backup);menu.add_cascade(label="Ustawienia",menu=settings)
        self.config(menu=menu)

    def _show_calendar(self):
        rows=[(r["due"] or "—",r["name"],r["institution"],f"{r['amount']:.2f} zł",r["category"],r["status"]) for r in payment_calendar(self.items,self.results)]
        TableWindow(self,"Kalendarz płatności",[("due","Termin",110),("name","Pozycja",210),("inst","Instytucja",180),("amount","Kwota",110),("cat","Kategoria",160),("status","Status",150)],rows)

    def _show_goals(self): GoalsWindow(self)
    def _show_wallets(self): WalletsWindow(self)

    def _show_limits(self):
        win=tk.Toplevel(self);win.title("Limity kategorii");win.geometry("900x600")
        root=ttk.Frame(win,padding=14);root.pack(fill="both",expand=True);ttk.Label(root,text="Limity kategorii",font=("Segoe UI",18,"bold")).pack(anchor="w")
        cols=("cat","limit","spent","planned","percent","status");tree=ttk.Treeview(root,columns=cols,show="headings")
        heads={"cat":"Kategoria","limit":"Limit","spent":"Wydano","planned":"Plan","percent":"Wykorzystanie","status":"Stan"}
        for k,w in zip(cols,(230,120,120,120,120,120)):tree.heading(k,text=heads[k]);tree.column(k,width=w,anchor="w")
        tree.pack(fill="both",expand=True,pady=(10,0))
        def fill():
            tree.delete(*tree.get_children())
            for r in category_limit_status(self.items,self.results):
                status="PRZEKROCZONY" if r["over"] else ("UWAGA" if r["warning"] else "OK")
                tree.insert("","end",iid=r["category"],values=(r["category"],"—" if not r["limit"] else f"{r['limit']:.2f} zł",f"{r['spent']:.2f} zł",f"{r['planned']:.2f} zł",f"{r['percent']:.1f}%",status))
        def edit():
            sel=tree.selection()
            if not sel: messagebox.showinfo("Limity","Zaznacz kategorię.",parent=win);return
            cat=sel[0];current=load_limits().get(cat,0.0);value=simpledialog.askfloat("Limit",f"Miesięczny limit dla: {cat}\n0 = usuń limit",initialvalue=current,minvalue=0,parent=win)
            if value is not None:set_limit(cat,value);fill();self._refresh_200()
        ttk.Button(root,text="Ustaw / zmień limit",command=edit).pack(anchor="w",pady=(10,0));fill()

    def _show_obligations(self):
        rows=[]
        for r in obligations_overview():
            rows.append((r["name"],r["bank"],f"{r['monthly']:.2f} zł",r["payment_day"],r["end_date"] or "—","—" if r["months_left"] is None else r["months_left"],f"{r['annual_cost']:.2f} zł",r["interest_type"],"AKTYWNE" if r["active"] else "ZAKOŃCZONE"))
        TableWindow(self,"Centrum zobowiązań",[("name","Zobowiązanie",190),("bank","Bank",130),("monthly","Miesięcznie",110),("day","Dzień",70),("end","Koniec",105),("left","Pozostało",90),("annual","Koszt roczny",120),("type","Rodzaj",120),("status","Status",110)],rows)

    def _show_next_forecast(self):
        data=next_month_forecast(self.items,load_history());lines=[f"Wpływy planowane: {data['income']:.2f} zł",f"Bieżący plan wydatków: {data['current_expenses']:.2f} zł",f"Prognoza kolejnego miesiąca: {data['projected_expenses']:.2f} zł",f"Prognozowany bilans: {data['projected_balance']:+.2f} zł","","Największe kategorie prognozy:"]
        for cat,val in list(data["categories"].items())[:8]:lines.append(f"• {cat}: {val:.2f} zł")
        messagebox.showinfo("Prognoza następnego miesiąca","\n".join(lines))

    def _show_intelligence(self):
        duplicates=detect_duplicate_transactions(self.transactions);anomalies=spending_anomalies(self.results,load_history());rows=[]
        for r in duplicates:rows.append(("DUPLIKAT",r["date"],r["counterparty"],f"{r['amount']:.2f} zł",f"{r['count']} podobne operacje"))
        for r in anomalies:rows.append(("ANOMALIA","",r["name"],f"{r['current']:.2f} zł",f"średnia {r['average']:.2f} zł / {r['change_percent']:+.1f}%"))
        TableWindow(self,"Inteligentna analiza",[("type","Typ",110),("date","Data",100),("name","Pozycja / kontrahent",260),("amount","Kwota",110),("info","Informacja",330)],rows)

    def _refresh_200(self):
        if hasattr(self,"home_vars"):
            self._refresh_home_dashboard()
        data=dashboard_200(self.items,self.results,self.transactions,load_history())
        if hasattr(self,"attention_var"):
            extra=[]
            if data["overdue_count"]: extra.append(f"⏰ Po terminie: {data['overdue_count']}")
            if data["review_count"]: extra.append(f"◆ Do zatwierdzenia: {data['review_count']}")
            if data["duplicate_count"]: extra.append(f"⧉ Podejrzane duplikaty: {data['duplicate_count']}")
            if data["anomaly_count"]: extra.append(f"▲ Anomalie kosztów: {data['anomaly_count']}")
            if extra:self.attention_var.set(self.attention_var.get()+"\n"+"\n".join(extra))

    def _compare(self):
        super()._compare();self._refresh_200()

    def _restore_state(self,state:dict):
        super()._restore_state(state)
        if hasattr(self,"home_vars"):self._refresh_200()

    def _sync_manual_installments(self):
        super()._sync_manual_installments()
        if hasattr(self,"home_vars"):self._refresh_200()


if __name__ == "__main__":
    PayCheck200App().mainloop()
