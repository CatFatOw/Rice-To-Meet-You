from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm  import Session
from database import get_db
from repository import final_visitor_repository
from datetime import date as Date
from models.final_visitor_tables import VisitorData
from schemas.final_visitor_schemas import FinalVisitorDataCreate, FinalVisitorDataResponse


router = APIRouter(prefix="/final_visitor", tags=["final_visitor"])

visitor_data_class = final_visitor_repository.VisitorRepository

@router.get("/all")
async def get_all(db:Session=Depends(get_db)):
    result = db.query(VisitorData).all()
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="NOT FOUND")
    return result

@router.get("/get-visitor-by-city-date")
async def get_visitor_data_by_city_date(
    city: str,
    date: Date,
    db: Session = Depends(get_db),
):
    repository = visitor_data_class(db)
    result = repository.getVisitorDataByCityDate(city, date)
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="NOTFOUND!")
    return result

# basic crud updates and deletes in case we need them
@router.post("/upload", response_model=FinalVisitorDataResponse, status_code=status.HTTP_201_CREATED)
async def add_new_visitor_data(visitor:FinalVisitorDataCreate, db:Session=Depends(get_db)):
    new_visitor = VisitorData(**visitor.model_dump())
    db.add(new_visitor)
    db.commit()
    db.refresh(new_visitor)
    return new_visitor

@router.put("/update/{id}", response_model=FinalVisitorDataResponse)
async def update_visitor(id:int, visitor:FinalVisitorDataCreate, db:Session=Depends(get_db)):
    data = db.query(VisitorData).filter(VisitorData.id == id).first()
    if not data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="ID NOT FOUND")

    for field, value in visitor.model_dump(exclude_unset=True).items():
        setattr(data, field, value)

    db.commit()
    db.refresh(data)
    return data

@router.delete("/delete/{id}",status_code=status.HTTP_204_NO_CONTENT)
async def delete_visitor_id(id:int, db:Session = Depends(get_db)):
    candidate = db.query(VisitorData).filter(VisitorData.id == id).first()
    if not candidate:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="candiate not found")
    db.delete(candidate)
    db.commit()
    



# @router.post("/upload_all_data")
# async def upload_all_data(file_path: str, db: Session = Depends(get_db)):
#     return final_visitor_repository.update_table(file_path, db)
